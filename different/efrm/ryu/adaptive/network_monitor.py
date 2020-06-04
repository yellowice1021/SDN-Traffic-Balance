# conding=utf-8
from __future__ import division
from operator import attrgetter
from ryu import cfg
from ryu.base import app_manager
from ryu.base.app_manager import lookup_service_brick
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, DEAD_DISPATCHER
from ryu.controller.handler import set_ev_cls
from ryu.ofproto import ofproto_v1_3
from ryu.lib import hub
import setting
import time
import random
import math
import numpy
from ryu.topology.switches import LLDPPacket
from ryu.lib.packet import lldp


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
        self.elephant_info = {}
        self.elephant_path = {}
        self.elephant_src = []
        self.monitor_time = 5
        self.monitor_number = 0
        self.flow_number = 0
        self.port_number = 0
        self.flow_size = 0
        self.port_size = 0
        self.flow_request_number = 0
        self.flow_request_size = 0
        self.port_request_number = 0
        self.port_request_size = 0
        self.flow_mode_number = 0
        self.flow_mode_size = 0
        self.flow_path_number = 0
        self.echo_latency = {}
        self.sw_module = lookup_service_brick('switches')
        self.awareness = lookup_service_brick('awareness')
        self.graph = None
        self.capabilities = None
        self.best_paths = None
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
            self.elephant_info = {}
            for dp in self.datapaths.values():
                self._request_stats(dp)
                self.capabilities = None
                self.best_paths = None
            self.ifChange = False
            self._send_echo_request()
            self.create_link_delay()
            hub.sleep(0.5)
            self.link_status()
            self.monitor_number = self.monitor_number + 1
            # self.link_status()
            # self.monitor_number = self.monitor_number + 1
            # self.logger.info("port number:" + str(self.port_number + self.port_request_number))
            # self.logger.info("flow number:" + str(self.flow_number + self.flow_request_number)
            # self.logger.info("port request number:" + str(self.port_request_number))
            # self.logger.info("flow request number:" + str(self.flow_request_number))
            # self.logger.info("flow mode number:" + str(self.flow_mode_number))
            self.logger.info("port size:" + str((self.port_size + self.port_request_size) / (1024 * 1024)))
            self.logger.info("flow size:" + str((self.flow_size + self.flow_request_size) / (1024 * 1024)))
            self.logger.info("all size:" + str((self.port_request_size + self.port_size + self.flow_request_size + self.flow_size) / (1024 * 1024)))
            self.logger.info("all number:" + str(self.port_request_number + self.port_number + self.flow_request_number + self.flow_number))
            # self.logger.info("flow request size:" + str(self.flow_request_size))
            # self.logger.info("flow mode size:" + str(self.flow_mode_size))
            # self.logger.info("flow path number:" + str(self.flow_path_number))
            hub.sleep(self.monitor_time)
            # self.show_stat()

    def _send_echo_request(self):
        """
            Seng echo request msg to datapath.
        """
        for datapath in self.datapaths.values():
            parser = datapath.ofproto_parser
            echo_req = parser.OFPEchoRequest(datapath,
                                             data="%.12f" % time.time())
            datapath.send_msg(echo_req)

            hub.sleep(0.05)

    @set_ev_cls(ofp_event.EventOFPEchoReply, MAIN_DISPATCHER)
    def echo_reply_handler(self, ev):
        """
            Handle the echo reply msg, and get the latency of link.
        """
        now_timestamp = time.time()
        try:
            latency = now_timestamp - eval(ev.msg.data)
            self.echo_latency[ev.msg.datapath.id] = latency
        except:
            return

    def get_delay(self, src, dst):
        """
            Get link delay.
                        Controller
                        |        |
        src echo latency|        |dst echo latency
                        |        |
                   SwitchA-------SwitchB

                    fwd_delay--->
                        <----reply_delay
            delay = (forward delay + reply delay - src datapath's echo latency
        """
        try:
            fwd_delay = self.awareness.graph[src][dst]['lldpdelay']
            re_delay = self.awareness.graph[dst][src]['lldpdelay']
            src_latency = self.echo_latency[src]
            dst_latency = self.echo_latency[dst]

            delay = (fwd_delay + re_delay - src_latency - dst_latency) / 2
            delay = round(delay, 6)
            return max(delay, 0)
        except:
            return float('inf')

    def _save_lldp_delay(self, src=0, dst=0, lldpdelay=0):
        try:
            self.awareness.graph[src][dst]['lldpdelay'] = lldpdelay
        except:
            if self.awareness is None:
                self.awareness = lookup_service_brick('awareness')
            return

    def create_link_delay(self):
        """
            Create link delay data, and save it into graph object.
        """
        try:
            for src in self.awareness.graph:
                for dst in self.awareness.graph[src]:
                    if src == dst:
                        self.awareness.graph[src][dst]['delay'] = 0
                        continue
                    delay = self.get_delay(src, dst)
                    self.awareness.graph[src][dst]['delay'] = delay
        except:
            if self.awareness is None:
                self.awareness = lookup_service_brick('awareness')
            return

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in_handler(self, ev):
        """
            Parsing LLDP packet and get the delay of link.
        """
        msg = ev.msg
        try:
            src_dpid, src_port_no = LLDPPacket.lldp_parse(msg.data)
            dpid = msg.datapath.id
            if self.sw_module is None:
                self.sw_module = lookup_service_brick('switches')

            for port in self.sw_module.ports.keys():
                if src_dpid == port.dpid and src_port_no == port.port_no:
                    delay = self.sw_module.ports[port].timestamp
                    if delay:
                        linkdelay = time.time() - delay
                        self._save_lldp_delay(src=src_dpid, dst=dpid,
                                            lldpdelay=linkdelay)
        except LLDPPacket.LLDPUnknownFormat as e:
            return

    def _request_stats(self, datapath):
        """
            Sending request msg to datapath
        """
        self.logger.debug('send stats request: %016x', datapath.id)
        ofproto = datapath.ofproto
        parser = datapath.ofproto_parser

        # req = parser.OFPPortDescStatsRequest(datapath, 0)
        # datapath.send_msg(req)

        req = parser.OFPPortStatsRequest(datapath, 0, ofproto.OFPP_ANY)
        datapath.send_msg(req)

        self.port_request_number = self.port_request_number + 1
        self.port_request_size = self.port_request_size + len(str(req))

        if str(datapath.id).startswith('2'):
            req = parser.OFPFlowStatsRequest(datapath)
            datapath.send_msg(req)

            self.flow_request_number = self.flow_request_number + 1
            self.flow_request_size = self.flow_request_size + len(str(req))

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

        self.flow_mode_number = self.flow_mode_number + 1
        self.flow_mode_size = self.flow_mode_size + len(str(dp))

    def send_flow_mod(self, datapath, flow_info, src_port, dst_port, flow_tcp, priority):
        """
            Build flow entry, and send it to datapath.
        """
        parser = datapath.ofproto_parser
        actions = []
        actions.append(parser.OFPActionOutput(dst_port))

        idle_timeout = 5

        if  flow_tcp == 'dst':
            match = parser.OFPMatch(
                in_port=src_port, eth_type=flow_info[0],
                ipv4_src=flow_info[1], ipv4_dst=flow_info[2])
        else:
            match = parser.OFPMatch(
                in_port=src_port, eth_type=flow_info[0],
                ipv4_src=flow_info[1], ipv4_dst=flow_info[2])

        self.add_flow(datapath, priority + 1, match, actions,
                      idle_timeout=5, hard_timeout=0)

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
            in_port = self.get_port(flow_info[1], access_table)
            self.send_flow_mod(first_dp, flow_info, in_port, out_port, 'dst', priority)
            self.send_flow_mod(first_dp, back_info, out_port, in_port, 'src', priority)

        # src and dst on the same datapath
        else:
            out_port = self.get_port(flow_info[2], access_table)
            in_port = self.get_port(flow_info[1], access_table)
            if out_port is None:
                self.logger.info("Out_port is None in same dp")
                return
            self.send_flow_mod(first_dp, flow_info, in_port, out_port, 'dst', priority)
            self.send_flow_mod(first_dp, back_info, out_port, in_port, 'src', priority)

    def find_new_path(self, src, dst, link_flow):
        """
            find new path for flow
        """
        shortest_paths = self.awareness.shortest_paths
        src_location = self.awareness.get_host_location(src)[0]
        dst_location = self.awareness.get_host_location(dst)[0]
        paths = shortest_paths.get(src_location).get(dst_location)
        speed = 6

        choose_paths = []
        choose_paths_main = {}
        choose_bandwidth_speed = 0
        choose_path = None
        choose_paths_speed = 0

        if (len(paths) > 1):
            for path in paths:
                path_length = len(path)
                min_bandwidth = setting.MAX_CAPACITY
                if path_length > 1:
                    for i in xrange(path_length - 1):
                        pre = path[i]
                        cur = path[i + 1]
                        link = (pre, cur)
                        (src_port, dst_port) = self.awareness.link_to_port[link]
                        link_left_bandwidth = self.port_info[(pre, src_port)]
                        min_bandwidth = min(link_left_bandwidth, min_bandwidth)
                if min_bandwidth > speed:
                    p = round((min_bandwidth - speed) / setting.MAX_CAPACITY, 4)
                    bandwidth_speed = round(1 / p, 2)
                    choose_paths.append((bandwidth_speed, path))
                    choose_paths_speed = choose_paths_speed + bandwidth_speed
            # self.logger.info(choose_paths)
            # self.logger.info(choose_paths_speed)

            for key in choose_paths:
                bandwidth_speed = key[0]
                bandwidth_speed_all = round((bandwidth_speed / choose_paths_speed), 2)
                bandwidth_speed_range = choose_bandwidth_speed + bandwidth_speed_all
                choose_paths_main[(choose_bandwidth_speed, bandwidth_speed_range)] = key[1]
                choose_bandwidth_speed = bandwidth_speed_range
            # self.logger.info(choose_paths_main)
            random_choose = random.uniform(0, 1)
            random_choose = round(random_choose, 2)

            for key in choose_paths_main:
                min_number = key[0]
                max_number = key[1]
                if min_number <= random_choose and max_number >= random_choose:
                    choose_path = choose_paths_main[key]
                    break

            # self.logger.info(choose_path)
            if choose_path:
                eth_type = link_flow[(src, dst)][1]
                priority = link_flow[(src, dst)][2]
                flow_info = (eth_type, src, dst)
                self.install_flow(self.datapaths, self.awareness.link_to_port, self.awareness.access_table, choose_path, flow_info, priority)
                self.logger.info("change path" + src + ' ' + dst + ' to ' + str(choose_path))
                path_length = len(choose_path)
                if path_length > 1:
                    for i in xrange(path_length - 1):
                        pre = choose_path[i]
                        cur = choose_path[i + 1]
                        link = (pre, cur)
                        (src_port, dst_port) = self.awareness.link_to_port[link]
                        self.port_info[(pre, src_port)] = self.port_info[(pre, src_port)] - speed
                        # self.logger.info(self.port_info[(pre, src_port)])
                # self.logger.info(self.elephant_path)
                # if (src, dst) not in self.elephant_path:
                #     path_length_old = len(paths)

                #     src_number = int(src.split('.')[1]) + int(src.split('.')[3])
                #     dst_number = int(dst.split('.')[1]) + int(dst.split('.')[3])

                #     random_number = (src_number + dst_number) % path_length_old

                #     main_path = paths[random_number]
                #     self.elephant_path[(src, dst)] = main_path

                main_path_old = self.elephant_path[(src, dst)]
                self.elephant_path[(src, dst)] = choose_path
                # self.logger.info(main_path_old)
                # self.logger.info(self.elephant_path)

                path_length_main = len(main_path_old)
                if path_length_main > 1:
                    for i in xrange(path_length_main - 1):
                        pre = main_path_old[i]
                        cur = main_path_old[i + 1]
                        link = (pre, cur)
                        (src_port, dst_port) = self.awareness.link_to_port[link]
                        self.port_info[(pre, src_port)] = self.port_info[(pre, src_port)] + speed
                        # self.logger.info(self.port_info[(pre, src_port)])

    def find_max_bandwidth(self, src, dst):
        """
            find max bandwidth of flow
        """
        shortest_paths = self.awareness.shortest_paths
        src_location = self.awareness.get_host_location(src)[0]
        dst_location = self.awareness.get_host_location(dst)[0]
        paths = shortest_paths.get(src_location).get(dst_location)

        max_bandwidth = 0
        max_bandwidth_path = paths[0]

        if (len(paths) > 1):
            for path in paths:
                path_length = len(path)
                min_bandwidth = setting.MAX_CAPACITY
                if path_length > 1:
                    for i in xrange(path_length - 1):
                        pre = path[i]
                        cur = path[i + 1]
                        link = (pre, cur)
                        (src_port, dst_port) = self.awareness.link_to_port[link]
                        link_left_bandwidth = self.port_info[(pre, src_port)]
                        min_bandwidth = min(link_left_bandwidth, min_bandwidth)
                        # self.logger.info(min_bandwidth)
                if min_bandwidth > max_bandwidth:
                    max_bandwidth = min_bandwidth
                    max_bandwidth_path = path

        max_bandwidth = setting.MAX_CAPACITY - max_bandwidth

        return max_bandwidth

    def change_flow_path(self, link, src, src_port):
        """
            find the flow and reroute flow
        """
        if link not in self.elephant_info:
            return
        link_flow = self.elephant_info[link]
        choose_flow = {}
        ifChoose = False

        for flow in link_flow:
            srcs = flow[0]
            dsts = flow[1]
            speed = link_flow[flow][0]
            ifChoose = True
            choose_flow[(srcs, dsts)] = speed
            # self.logger.info(max_bandwidth)
            # self.logger.info(carry_bandwidth)
            # self.logger.info(speed)

        if ifChoose:
            sorted(choose_flow)
            # self.logger.info(choose_flow)
            choose_src_dst = choose_flow.keys()
        #     # self.logger.info(choose_src_dst)
            bandwidth = self.port_info[(src, src_port)]
            i = len(choose_src_dst)
            j = 0
            while bandwidth < setting.MAX_CAPACITY * 0.1:
                if j == i - 1:
                    break
                flow = choose_src_dst[j]
                src_ip = flow[0]
                dst_ip = flow[1]
                # self.logger.info(flow)
                self.find_new_path(src_ip, dst_ip, link_flow)
                bandwidth = self.port_info[(src, src_port)]
                if bandwidth < setting.MAX_CAPACITY * 0.1:
                    break
        #         choose_src_dst.pop(i)
                # self.flow_path_number = self.flow_path_number + 1
                # self.logger.info(bandwidth)
                # self.logger.info(j)
                j = j + 1

    def link_status(self):
        """
            check load of links
        """
        bandwidth_number = 0
        link_number = 0
        bandwidth_all_max = 0

        for link in self.awareness.link_to_port:
            (src, dst) = link
            (src_port, dst_port) = self.awareness.link_to_port[link]
            bandwidth = self.port_info[(src, src_port)]
            if bandwidth < setting.MAX_CAPACITY * 0.1:
                # self.logger.info(link)
                self.change_flow_path(link, src, src_port)
                self.flow_path_number = self.flow_path_number + 1
            bandwidth_all = (setting.MAX_CAPACITY - self.port_info[(src, src_port)]) / setting.MAX_CAPACITY
            bandwidth_all = round(bandwidth_all, 2)
            if bandwidth_all > bandwidth_all_max:
                bandwidth_all_max = bandwidth_all
            link_number = link_number + 1
            bandwidth_number = bandwidth_number + bandwidth_all
        if link_number != 0:
            monitor_time = 0.6 * bandwidth_all_max + 0.4 * round((bandwidth_number / link_number), 2)
            if monitor_time != 0:
                monitor_time = round(monitor_time, 2)
                monitor_time = - 10 * numpy.log2(0.9)
                if monitor_time > 20:
                    monitor_time = 20
                if monitor_time < 3:
                    monitor_time = 2
                self.monitor_time = int(monitor_time)
            # self.monitor_time = int(monitor_time)
        #         # if self.monitor_number < 7:
        #         #     self.monitor_time = 5
        #     # else:
        #     #     self.monitor_time = 20
            self.logger.info(monitor_time)

    def find_bandwidth_delay_path(self, src, dst):
        """
          find path for flow
        """
        shortest_paths = self.awareness.shortest_paths
        src_location = self.awareness.get_host_location(src)[0]
        dst_location = self.awareness.get_host_location(dst)[0]
        paths = shortest_paths.get(src_location).get(dst_location)
        select_paths = {}
        score_paths = {}
        b = []
        w = []
        d = []

        max_bandwidth_path = paths[0]
        t = 0

        if (len(paths) > 1):
            for path in paths:
                select_paths[t] = path
                delay = 0
                max_bandwidth = 0
                path_length = len(path)
                min_bandwidth = setting.MAX_CAPACITY
                if path_length > 1:
                    for i in xrange(path_length - 1):
                        pre = path[i]
                        cur = path[i + 1]
                        link = (pre, cur)
                        (src_port, dst_port) = self.awareness.link_to_port[link]
                        link_left_bandwidth = self.port_info[(pre, src_port)]
                        delay = delay + self.awareness.graph[pre][cur]['delay']
                        # self.logger.info(delay)
                        # min_bandwidth = min(link_left_bandwidth, min_bandwidth)
                        # self.logger.info(min_bandwidth)
                        if min_bandwidth > link_left_bandwidth:
                            min_bandwidth = link_left_bandwidth
                        if max_bandwidth < link_left_bandwidth:
                            max_bandwidth = link_left_bandwidth
                # score_paths[t] = (min_bandwidth, max_bandwidth, delay)
                b.append(min_bandwidth)
                w.append(max_bandwidth)
                d.append(delay)
                t = t + 1

        # self.logger.info(select_paths)
        max_b = max(b)
        min_b = min(b)
        max_w = max(w)
        min_w = min(w)
        max_d = max(d)
        min_d = min(d)
        for i in range(0, len(b)):
            if max_b == min_b:
                b[i] = 1
            else:
                b[i] = (b[i] - min_b) / (max_b - min_b)
        for i in range(0, len(w)):
            if max_w == min_w:
                w[i] = 1
            else:
                w[i] = (w[i] - min_w) / (max_w - min_w)
        for i in range(0, len(d)):
            if max_d == min_d:
                d[i] = 1
            else:
                d[i] = (max_d - d[i]) / (max_d - min_d)

        path_number = len(select_paths)
        score = 0
        best_path = select_paths[0]
        for i in xrange(0, path_number):
            path_score = 0.5 * b[i] + 0.25 * w[i] + 0.25 * d[i]
            if path_score > score:
                score = path_score
                best_path = select_paths[i]
        # self.logger.info(best_path)

        return best_path

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
        self.flow_stats.setdefault(dpid, {})

        if str(dpid).startswith('2'):
            self.flow_number = self.flow_number + 1
            self.flow_size = self.flow_size + len(str(ev.msg))

            for stat in sorted([flow for flow in body if ((flow.priority not in [0, 65535]) and (flow.match.get('ipv4_src')) and (flow.match.get('ipv4_dst')))],
                               key=lambda flow: (flow.match.get('in_port'),
                                                 flow.match.get('ipv4_dst'))):
                src = str(stat.match.get('ipv4_src'))
                dst = str(stat.match.get('ipv4_dst'))
                if str(dpid).startswith('2'):
                    in_port = stat.match.get('in_port')
                    out_port = stat.instructions[0].actions[0].port
                    priority = stat.priority
                    key = (dpid, src, dst, priority)
                    value = (stat.byte_count, time.time())
                    self._save_stats(self.flow_stats[dpid], key, value, 2)

                    pre = 0
                    period = self.monitor_time + 0.5
                    tmp = self.flow_stats[dpid][key]
                    now = tmp[-1][0]
                    if len(tmp) > 1:
                        pre = tmp[-2][0]
                        period = tmp[-1][1] - tmp[-2][1]

                    data = (now - pre) * 8 / (1024 * 1024)
                    speed = round(data / period, 2)

                    # self.logger.info(period)
                    # self.logger.info(key)
                    # self.logger.info(speed)

                    if speed > 0:
                        if speed > setting.MAX_CAPACITY * 0.1:
                            src_dpid = self.awareness.link_in_to[(dpid, in_port)]
                            dst_dpid = self.awareness.link_in_to[(dpid, out_port)]
                            eth_type = stat.match.get('eth_type')
                            priority = stat.priority
                            # self.logger.info(key)
                            if (src, dst) in self.elephant_src:
                                # self.logger.info(key)
                                if (src_dpid, dpid) not in self.elephant_info:
                                    self.elephant_info[(src_dpid, dpid)] = {}
                                if (dpid, dst_dpid) not in self.elephant_info:
                                    self.elephant_info[(dpid, dst_dpid)] = {}
                                self.elephant_info[(src_dpid, dpid)][(src, dst)] = (speed, eth_type, priority)
                                self.elephant_info[(dpid, dst_dpid)][(src, dst)] = (speed, eth_type, priority)
                                # self.logger.info(self.elephant_info)
                                # self.elephant_info[key] = speed


    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def _port_stats_reply_handler(self, ev):
        """
            Save port's stats info
            Calculate port's speed and save it.
        """
        body = ev.msg.body
        dpid = ev.msg.datapath.id

        self.port_number = self.port_number + 1
        self.port_size = self.port_size + len(str(ev.msg))

        for stat in sorted(body, key=attrgetter('port_no')):
            port_no = stat.port_no
            if port_no != ofproto_v1_3.OFPP_LOCAL:
                key = (dpid, port_no)
                value = (stat.tx_bytes, stat.rx_bytes, time.time())

                self._save_stats(self.port_stats, key, value, 2)

                # Get port speed.
                tmp = self.port_stats[key]

                if key not in self.port_info:
                    self.port_info[key] = 0

                if len(tmp) > 1:

                    preTx = tmp[-2][0]
                    nowTx = tmp[-1][0]
                    preTime = tmp[-2][2]
                    nowTime = tmp[-1][2]
                    datas = (nowTx - preTx) * 8 / (1024 * 1024)
                    times = nowTime - preTime
                    speedTx = round(datas / times, 2)

                    # self.logger.info(times)

                    bandwidth = setting.MAX_CAPACITY - speedTx
                    self.port_info[key] = bandwidth

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