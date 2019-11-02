# conding=utf-8
from __future__ import division
import copy
from operator import attrgetter
from ryu import cfg
from ryu.base import app_manager
from ryu.base.app_manager import lookup_service_brick
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import CONFIG_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
from ryu.lib.packet import packet
import setting
import time
import heapq


CONF = cfg.CONF


class NetworkMonitor(app_manager.RyuApp):
    """
        NetworkMonitor is a Ryu app for collecting traffic information.

    """
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(NetworkMonitor, self).__init__(*args, **kwargs)
        self.name = 'monitor'
        self.datapaths = {}
        self.port_stats = {}
        self.port_info = {}
        self.flow_stats = {}
        self.flow_speed = {}
        self.stats = {}
        self.port_features = {}
        self.free_bandwidth = {}
        self.link_info = {}
        self.link_info_flag = False
        self.link_elephant_flow = {}
        self.elephant_info = []
        self.elephant_path = []
        self.elephant_path_info = {}
        self.elephant_path_bandwidth = {}
        self.elephant_path_speed = {}
        self.elephant_path_switch = {}
        self.ifChange = False
        self.awareness = lookup_service_brick('awareness')
        self.graph = None
        self.capabilities = None
        self.best_paths = None
        # Start to green thread to monitor traffic and calculating
        # free bandwidth of links respectively.
        self.monitor_thread = hub.spawn(self._monitor)

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def _state_change_handler(self, ev):
        """
            Record datapath's info
        """
        datapath = ev.datapath
        if ev.state == MAIN_DISPATCHER:
            if not datapath.id in self.datapaths:
                self.logger.debug('register datapath: %016x', datapath.id)
                self.datapaths[datapath.id] = datapath
        elif ev.state == DEAD_DISPATCHER:
            if datapath.id in self.datapaths:
                self.logger.debug('unregister datapath: %016x', datapath.id)
                del self.datapaths[datapath.id]

    def _monitor(self):
        """
            Main entry method of monitoring traffic.
        """
        while True:
            self.stats['flow'] = {}
            self.stats['port'] = {}
            for dp in self.datapaths.values():
                self.port_features.setdefault(dp.id, {})
                self._request_stats(dp)
                # refresh data.
                self.capabilities = None
                self.best_paths = None
            self.link_elephant_flow = {}
            # self.elephant_info = []
            self.ifChange = False
            hub.sleep(0.5)
            self.elephant_path_status()
            hub.sleep(setting.MONITOR_PERIOD)
            # self.show_stat()

    def _request_stats(self, datapath):
        """
            Sending request msg to datapath
        """
        self.logger.debug('send stats request: %016x', datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        req = parser.OFPPortDescStatsRequest(datapath, 0)
        datapath.send_msg(req)

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

        req = parser.OFPFlowStatsRequest(datapath)
        datapath.send_msg(req)

    def get_path_bandwidth_elephant(self, paths, ip_src, ip_dst, src, dst):
        """
            get with with max bandwidth and min elephant
        """

        link_bandwidth = setting.MAX_CAPACITY
        max_elephant_bandwidth = 0
        min_elephant_path = paths[0]

        if(len(paths) > 1):
            for path in paths:
                path_length = len(path)
                min_equal_bandwidth = link_bandwidth
                for i in xrange(path_length - 1):
                    pre = path[i]
                    cur = path[i + 1]
                    link = (pre, cur)
                    (src_port, dst_port) = self.awareness.link_to_port[link]
                    if link in self.link_elephant_flow:
                        elephant_number = self.link_elephant_flow[link]
                    else:
                        elephant_number = 0
                    link_left_bandwidth = self.free_bandwidth[pre][src_port]
                    equal_bandwidth = link_left_bandwidth / 1
                    min_equal_bandwidth = min(equal_bandwidth, min_equal_bandwidth)
                    # self.logger.info(link)
                    # self.logger.info(link_left_bandwidth)
                    # self.logger.info(equal_bandwidth)
                if min_equal_bandwidth > max_elephant_bandwidth:
                    max_elephant_bandwidth = min_equal_bandwidth
                    min_elephant_path = path
                # self.logger.info(path)
                # self.logger.info(min_equal_bandwidth)

        path_length = len(min_elephant_path)
        for i in xrange(path_length - 1):
            pre = min_elephant_path[i]
            cur = min_elephant_path[i + 1]
            link = (pre, cur)
            # if (ip_src, ip_dst) not in self.elephant_info:
            if link in self.link_elephant_flow:
                self.link_elephant_flow[link] = self.link_elephant_flow[link] + 1
            else:
                self.link_elephant_flow[link] = 1
            if link not in self.elephant_path:
                self.elephant_path.append(link)
            if link not in self.elephant_path_info:
                self.elephant_path_info[link] = []
            if link not in self.elephant_path_bandwidth:
                self.elephant_path_bandwidth[link] = []
            self.elephant_path_info[link].append((ip_src, ip_dst))

        if (ip_src, ip_dst) not in self.elephant_info:
            self.elephant_info.append((ip_src, ip_dst))
            self.elephant_path_switch[(ip_src, ip_dst)] = min_elephant_path

        # self.logger.info(self.link_elephant_flow)
        # self.logger.info(self.elephant_path)
        # self.logger.info(self.elephant_info)
        # self.logger.info(self.elephant_path_info)
        # self.logger.info(self.elephant_path_switch)

        return min_elephant_path

    def get_port(self, dst_ip, access_table):
        """
            Get access port if dst host.
            access_table: {(sw,port) :(ip, mac)}
        """
        if access_table:
            if isinstance(access_table.values()[0], tuple):
                for key in access_table.keys():
                    if dst_ip == access_table[key][0]:
                        dst_port = key[1]
                        return dst_port
        return None

    def add_flow(self, dp, p, match, actions, idle_timeout=0, hard_timeout=0):
        """
            Send a flow entry to datapath.
        """
        ofproto = dp.ofproto
        parser = dp.ofproto_parser

        inst = [parser.OFPInstructionActions(ofproto.OFPIT_APPLY_ACTIONS,
                                             actions)]

        mod = parser.OFPFlowMod(datapath=dp, priority=p,
                                idle_timeout=idle_timeout,
                                hard_timeout=hard_timeout,
                                match=match, instructions=inst)
        dp.send_msg(mod)

    def send_flow_mod(self, datapath, flow_info, src_port, dst_port, flow_tcp, priority):
        """
            Build flow entry, and send it to datapath.
        """
        parser = datapath.ofproto_parser
        actions = []
        actions.append(parser.OFPActionOutput(dst_port))

        if  flow_tcp == 'dst':
            match = parser.OFPMatch(
                in_port=src_port, eth_type=flow_info[0],
                ipv4_src=flow_info[1], ipv4_dst=flow_info[2], ip_proto=17, udp_dst=5001)
        else:
            match = parser.OFPMatch(
                in_port=src_port, eth_type=flow_info[0],
                ipv4_src=flow_info[1], ipv4_dst=flow_info[2], ip_proto=17, udp_src=5001)

        self.add_flow(datapath, priority + 1, match, actions,
                      idle_timeout=15, hard_timeout=120)

    def get_port_pair_from_link(self, link_to_port, src_dpid, dst_dpid):
        """
            Get port pair of link, so that controller can install flow entry.
        """
        if (src_dpid, dst_dpid) in link_to_port:
            return link_to_port[(src_dpid, dst_dpid)]
        else:
            self.logger.info("dpid:%s->dpid:%s is not in links" % (
                             src_dpid, dst_dpid))
            return None

    def install_flow(self, datapaths, link_to_port, access_table, path,
                     flow_info, priority):
        '''
            Install flow entires for roundtrip: go and back.
            @parameter: path=[dpid1, dpid2...]
                        flow_info=(eth_type, src_ip, dst_ip, in_port)
        '''
        if path is None or len(path) == 0:
            self.logger.info("Path error!")
            return
        in_port = flow_info[3]
        first_dp = datapaths[path[0]]
        out_port = first_dp.ofproto.OFPP_LOCAL
        back_info = (flow_info[0], flow_info[2], flow_info[1])

        # inter_link
        if len(path) > 2:
            for i in xrange(1, len(path)-1):
                port = self.get_port_pair_from_link(link_to_port,
                                                    path[i-1], path[i])
                port_next = self.get_port_pair_from_link(link_to_port,
                                                         path[i], path[i+1])
                if port and port_next:
                    src_port, dst_port = port[1], port_next[0]
                    datapath = datapaths[path[i]]
                    self.send_flow_mod(datapath, flow_info, src_port, dst_port, 'dst', priority)
                    self.send_flow_mod(datapath, back_info, dst_port, src_port, 'src', priority)
                    self.logger.debug("inter_link flow install")
        if len(path) > 1:
            # the last flow entry: tor -> host
            port_pair = self.get_port_pair_from_link(link_to_port,
                                                     path[-2], path[-1])
            if port_pair is None:
                self.logger.info("Port is not found")
                return
            src_port = port_pair[1]

            dst_port = self.get_port(flow_info[2], access_table)
            if dst_port is None:
                self.logger.info("Last port is not found.")
                return

            last_dp = datapaths[path[-1]]
            self.send_flow_mod(last_dp, flow_info, src_port, dst_port, 'dst', priority)
            self.send_flow_mod(last_dp, back_info, dst_port, src_port, 'src', priority)

            # the first flow entry
            port_pair = self.get_port_pair_from_link(link_to_port,
                                                     path[0], path[1])
            if port_pair is None:
                self.logger.info("Port not found in first hop.")
                return
            out_port = port_pair[0]
            self.send_flow_mod(first_dp, flow_info, in_port, out_port, 'dst', priority)
            self.send_flow_mod(first_dp, back_info, out_port, in_port, 'src', priority)

        # src and dst on the same datapath
        else:
            out_port = self.get_port(flow_info[2], access_table)
            if out_port is None:
                self.logger.info("Out_port is None in same dp")
                return
            self.send_flow_mod(first_dp, flow_info, in_port, out_port, 'dst', priority)
            self.send_flow_mod(first_dp, back_info, out_port, in_port, 'src', priority)

    def elephant_new_path(self, key, speed, data):
        """
            find a new path for elephant flow
        """
        old_path = self.elephant_path_switch[key]
        src = old_path[0]
        dst = old_path[-1]
        shortest_paths = self.awareness.shortest_paths
        paths = shortest_paths.get(src).get(dst)

        link_bandwidth = setting.MAX_CAPACITY
        max_elephant_bandwidth = 0
        min_elephant_path = paths[0]

        if (len(paths) > 1):
            for path in paths:
                path_length = len(path)
                min_equal_bandwidth = link_bandwidth
                for i in xrange(path_length - 1):
                    pre = path[i]
                    cur = path[i + 1]
                    link = (pre, cur)
                    (src_port, dst_port) = self.awareness.link_to_port[link]
                    if link in self.link_elephant_flow:
                        elephant_number = self.link_elephant_flow[link]
                    else:
                        elephant_number = 0
                    link_left_bandwidth = self.free_bandwidth[pre][src_port]
                    equal_bandwidth = link_left_bandwidth / (elephant_number + 1)
                    min_equal_bandwidth = min(equal_bandwidth, min_equal_bandwidth)
                    # self.logger.info(link)
                    # self.logger.info(link_left_bandwidth)
                    # self.logger.info(equal_bandwidth)
                if min_equal_bandwidth > max_elephant_bandwidth:
                    max_elephant_bandwidth = min_equal_bandwidth
                    min_elephant_path = path
                # self.logger.info(path)
                # self.logger.info(min_equal_bandwidth)
            if max_elephant_bandwidth > speed:
                self.ifChange = True
                eth_type = self.elephant_path_speed[data][1]
                in_port = self.elephant_path_speed[data][2]
                priority = self.elephant_path_speed[data][3]
                flow_info = (eth_type, key[0], key[1], in_port)
                self.logger.info('path change:%s to %s: %s' % (key[0], key[1], min_elephant_path))
                self.install_flow(self.datapaths, self.awareness.link_to_port, self.awareness.access_table, min_elephant_path, flow_info, priority)

                length = len(old_path)
                for i in xrange(length - 1):
                    pre = old_path[i]
                    cur = old_path[i + 1]
                    link = (pre, cur)
                    info = self.elephant_path_info[link]
                    info_length = len(info)
                    if info_length == 1:
                        self.elephant_path.remove(link)
                        self.elephant_path_bandwidth.pop(link)
                    self.elephant_path_info[link].remove((key[0], key[1]))

                path_length = len(min_elephant_path)
                for i in xrange(path_length - 1):
                    pre = min_elephant_path[i]
                    cur = min_elephant_path[i + 1]
                    link = (pre, cur)
                    # if (ip_src, ip_dst) not in self.elephant_info:
                    if link in self.link_elephant_flow:
                        self.link_elephant_flow[link] = self.link_elephant_flow[link] + 1
                    else:
                        self.link_elephant_flow[link] = 1
                    if link not in self.elephant_path:
                        self.elephant_path.append(link)
                    if link not in self.elephant_path_info:
                        self.elephant_path_info[link] = []
                    if link not in self.elephant_path_bandwidth:
                        self.elephant_path_bandwidth[link] = []
                    self.elephant_path_info[link].append((key[0], key[1]))

                if (key[0], key[1]) not in self.elephant_info:
                    self.elephant_info.append((key[0], key[1]))

                self.elephant_path_switch[(key[0], key[1])] = min_elephant_path

                # self.logger.info(self.link_elephant_flow)
                # self.logger.info(self.elephant_path)
                # self.logger.info(self.elephant_path_info)
                # self.logger.info(self.elephant_path_bandwidth)
                # self.logger.info(self.elephant_info)
                # self.logger.info(self.elephant_path_switch)

    def elephant_path_new(self, link):
        """
            find the max bandwidth elephant flow in the link
        """
        max_speed = 0
        data_flow = self.elephant_path_info[link][0]
        data_key = (link[0], data_flow[0], data_flow[1])
        for data in self.elephant_path_info[link]:
            dpid = link[0]
            src = data[0]
            dst = data[1]
            key = (dpid, src, dst)
            speed = self.elephant_path_speed[key][0]
            if speed > max_speed:
                max_speed = speed
                data_flow = (src, dst)
                data_key = key
        self.elephant_new_path(data_flow, max_speed, data_key)

    def elephant_path_status(self):
        """
            check link if overhead
        """

        for link in self.elephant_path:
            if self.ifChange == True:
                break
            (src, dst) = link
            (src_port, dst_port) = self.awareness.link_to_port[link]
            link_left_bandwidth = self.free_bandwidth[src][src_port]
            self.elephant_path_bandwidth[link].append(round(link_left_bandwidth, 2))
            if len(self.elephant_path_bandwidth[link]) > 3:
                self.elephant_path_bandwidth[link].pop(0)
            if len(self.elephant_path_info[link]) != 1:
                if len(self.elephant_path_bandwidth[link]) == 3:
                    path_bandwidth = (self.elephant_path_bandwidth[link][0] + self.elephant_path_bandwidth[link][1] + self.elephant_path_bandwidth[link][2]) / 3
                    if path_bandwidth < setting.MAX_CAPACITY * 0.1:
                        self.logger.info(path_bandwidth)
                        self.elephant_path_new(link)
            self.logger.info(self.elephant_path_bandwidth[link])

    def save_freebandwidth(self, dpid, port_no, speed):
        free_bw = setting.MAX_CAPACITY - speed
        self.free_bandwidth[dpid].setdefault(port_no, None)
        self.free_bandwidth[dpid][port_no] = free_bw

    def _save_stats(self, _dict, key, value, length):
        if key not in _dict:
            _dict[key] = []
        _dict[key].append(value)

        if len(_dict[key]) > length:
            _dict[key].pop(0)

    def _get_speed(self, now, pre, period):
        if period:
            return (now - pre) / (period)
        else:
            return 0

    def _get_free_bw(self, capacity, speed):
        # BW:Mbit/s
        return max(capacity/10**3 - speed * 8/10**6, 0)

    def _get_time(self, sec, nsec):
        return sec + nsec / (10 ** 9)

    def _get_period(self, n_sec, n_nsec, p_sec, p_nsec):
        return self._get_time(n_sec, n_nsec) - self._get_time(p_sec, p_nsec)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def _flow_stats_reply_handler(self, ev):
        """
            Save flow stats reply info into self.flow_stats.
            Calculate flow speed and Save it.
        """
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        self.stats['flow'][dpid] = body
        self.flow_stats.setdefault(dpid, {})
        self.flow_speed.setdefault(dpid, {})
        for stat in sorted([flow for flow in body if flow.priority >= 40 and flow.priority <= 100],
                           key=lambda flow: (flow.match.get('in_port'),
                                             flow.match.get('ipv4_dst'))):
            src = str(stat.match.get('ipv4_src'))
            dst = str(stat.match.get('ipv4_dst'))
            if (src, dst) in self.elephant_info:
                key = (dpid, src, dst)
                value = (stat.packet_count, stat.byte_count,
                         stat.duration_sec, stat.duration_nsec)
                self._save_stats(self.flow_stats[dpid], key, value, 5)

                # Get flow's speed.
                pre = 0
                period = setting.MONITOR_PERIOD
                tmp = self.flow_stats[dpid][key]
                if len(tmp) > 1:
                    pre = tmp[-2][1]
                    now = tmp[-1][1]
                    data = (now - pre) * 8 / (1024 * 1024)
                    period = self._get_period(tmp[-1][2], tmp[-1][3],
                                              tmp[-2][2], tmp[-2][3])

                    speed = round(data / period, 2)
                    eth_type = stat.match.get('eth_type')
                    in_port = stat.match.get('in_port')
                    priority = stat.priority
                    self.elephant_path_speed[key] = (speed, eth_type, in_port, priority)
                    # self.logger.info(self.elephant_path_speed)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        """
            Save port's stats info
            Calculate port's speed and save it.
        """
        body = ev.msg.body
        dpid = ev.msg.datapath.id
        self.stats['port'][dpid] = body
        self.free_bandwidth.setdefault(dpid, {})

        for stat in sorted(body, key=attrgetter('port_no')):
            port_no = stat.port_no
            if port_no != ofproto_v1_3.OFPP_LOCAL:
                key = (dpid, port_no)
                value = (stat.tx_bytes, stat.rx_bytes, stat.rx_errors,
                         stat.duration_sec, stat.duration_nsec, time.time())

                self._save_stats(self.port_stats, key, value, 5)

                # Get port speed.
                tmp = self.port_stats[key]

                if key not in self.port_info:
                    self.port_info[key] = {}
                    self.port_info[key]['speedTx'] = 0
                    self.port_info[key]['speedRx'] = 0

                if len(tmp) > 1:

                    # txBytes
                    preTx = tmp[-2][0]
                    nowTx = tmp[-1][0]
                    preTime = tmp[-2][5]
                    nowTime = tmp[-1][5]
                    datas = (nowTx - preTx) * 8 / (1024 * 1024)
                    times = nowTime - preTime
                    speedTx = round(datas / times, 2)

                    self.save_freebandwidth(dpid, port_no, speedTx)

    @set_ev_cls(ofp_event.EventOFPPortDescStatsReply, MAIN_DISPATCHER)
    def port_desc_stats_reply_handler(self, ev):
        """
            Save port description info.
        """
        msg = ev.msg
        dpid = msg.datapath.id
        ofproto = msg.datapath.ofproto

        config_dict = {ofproto.OFPPC_PORT_DOWN: "Down",
                       ofproto.OFPPC_NO_RECV: "No Recv",
                       ofproto.OFPPC_NO_FWD: "No Farward",
                       ofproto.OFPPC_NO_PACKET_IN: "No Packet-in"}

        state_dict = {ofproto.OFPPS_LINK_DOWN: "Down",
                      ofproto.OFPPS_BLOCKED: "Blocked",
                      ofproto.OFPPS_LIVE: "Live"}

        ports = []
        for p in ev.msg.body:
            ports.append('port_no=%d hw_addr=%s name=%s config=0x%08x '
                         'state=0x%08x curr=0x%08x advertised=0x%08x '
                         'supported=0x%08x peer=0x%08x curr_speed=%d '
                         'max_speed=%d' %
                         (p.port_no, p.hw_addr,
                          p.name, p.config,
                          p.state, p.curr, p.advertised,
                          p.supported, p.peer, p.curr_speed,
                          p.max_speed))

            if p.config in config_dict:
                config = config_dict[p.config]
            else:
                config = "up"

            if p.state in state_dict:
                state = state_dict[p.state]
            else:
                state = "up"

            port_feature = (config, state, p.curr_speed)
            self.port_features[dpid][p.port_no] = port_feature

    @set_ev_cls(ofp_event.EventOFPPortStatus, MAIN_DISPATCHER)
    def _port_status_handler(self, ev):
        """
            Handle the port status changed event.
        """
        msg = ev.msg
        reason = msg.reason
        port_no = msg.desc.port_no
        dpid = msg.datapath.id
        ofproto = msg.datapath.ofproto

        reason_dict = {ofproto.OFPPR_ADD: "added",
                       ofproto.OFPPR_DELETE: "deleted",
                       ofproto.OFPPR_MODIFY: "modified", }

        if reason in reason_dict:

            print "switch%d: port %s %s" % (dpid, reason_dict[reason], port_no)
        else:
            print "switch%d: Illeagal port state %s %s" % (port_no, reason)

    @set_ev_cls(ofp_event.EventOFPFlowRemoved, MAIN_DISPATCHER)
    def flow_removed_handler(self, ev):
        msg = ev.msg
        dp = msg.datapath
        ofp = dp.ofproto

        if msg.reason == ofp.OFPRR_IDLE_TIMEOUT:
            reason = 'IDLE TIMEOUT'
        elif msg.reason == ofp.OFPRR_HARD_TIMEOUT:
            reason = 'HARD TIMEOUT'
        elif msg.reason == ofp.OFPRR_DELETE:
            reason = 'DELETE'
        elif msg.reason == ofp.OFPRR_GROUP_DELETE:
            reason = 'GROUP DELETE'
        else:
            reason = 'unknown'

        self.logger.debug('OFPFlowRemoved received: '
                          'cookie=%d priority=%d reason=%s table_id=%d '
                          'duration_sec=%d duration_nsec=%d '
                          'idle_timeout=%d hard_timeout=%d '
                          'packet_count=%d byte_count=%d match.fields=%s',
                          msg.cookie, msg.priority, reason, msg.table_id,
                          msg.duration_sec, msg.duration_nsec,
                          msg.idle_timeout, msg.hard_timeout,
                          msg.packet_count, msg.byte_count, msg.match)

    def show_stat(self):
        '''
            Show statistics info according to data type.
            type: 'port' 'flow'
        '''
        if setting.TOSHOW is False:
            return

        if(self.stats['flow']):
            bodys = self.stats['flow']
            print('datapath ''  port    ip-dst      '
                  'out-port packets  bytes  flow-speed(B/s)')
            print('---------------- ''  -------- ----------------- '
                  '-------- -------- -------- -----------')
            for dpid in bodys.keys():
                for stat in sorted(
                    [flow for flow in bodys[dpid] if flow.priority == 1],
                    key=lambda flow: (flow.match.get('in_port'),
                                      flow.match.get('ipv4_dst'))):
                    print('%6s %6x %10s %8x %8d %8d %8.1f' % (
                        dpid,
                        stat.match['in_port'], stat.match['ipv4_dst'],
                        stat.instructions[0].actions[0].port,
                        stat.packet_count, stat.byte_count,
                        abs(self.flow_speed[dpid][
                            (stat.match.get('in_port'),
                            stat.match.get('ipv4_dst'),
                            stat.instructions[0].actions[0].port)][-1])))
            print '\n'

        if(self.stats['port']):
            bodys = self.stats['port']
            print('datapath  port   ''rx-pkts  rx-bytes '
                  'tx-pkts  tx-bytes rx-speed(Mbit/s)'
                  ' tx-speed(Mbit/s)  ')
            print('----------------   -------- ''-------- --------'
                  '-------- --------'
                  '----------------  ----------------   ')
            format = '%6s %6x %8d %8d %8d %8d    %8.2f    %8.2f'
            for dpid in bodys.keys():
                for stat in sorted(bodys[dpid], key=attrgetter('port_no')):
                    if stat.port_no != ofproto_v1_3.OFPP_LOCAL:
                        print(format % (
                            dpid, stat.port_no,
                            stat.rx_packets, stat.rx_bytes,
                            stat.tx_packets, stat.tx_bytes,
                            self.port_info[(dpid, stat.port_no)]['speedRx'],
                            self.port_info[(dpid, stat.port_no)]['speedTx'],))
            print '\n'

        # Show the bandwidth of links
        if(self.link_info_flag == True):
            print('src        dst      bandwidth(Mbit/s)    freebandwidth(Mbit/s')
            format = '%2s %10s %16.2f %16.2f'
            for link in self.awareness.link_to_port:
                (src_dpid, dst_dpid) = link
                bandwidth = self.link_info[link]['bandwidth']
                freebandwidth = self.link_info[link]['freebandwidth']
                print(format % (src_dpid, dst_dpid, bandwidth, freebandwidth))
        # for link in self.awareness.link_to_port:
        #     (src_dpid, dst_dpid) = link
        #     self.logger.info(src_dpid)
        #     self.logger.info(dst_dpid)
        #     if(self.link_info_flag == True):
        #         self.logger.info(self.link_info[link]['bandwidth'])
