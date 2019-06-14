from mininet.net import Mininet
from mininet.log import setLogLevel
from mininet.link import Link, Intf, TCLink
from mininet.topo import Topo
from mininet.cli import CLI

import os
import logging
import time
from subprocess import Popen
from multiprocessing import Process

import sys
sys.path.insert(0, './peers/')
import randoms
import stag_01_02
import stag_02_03
import stag_03_03
import stag_04_03
import stride_1
import stride_2
import stride_4
import stride_8
import hotspot

class Fattree(Topo):
	"""
		Class of Fattree Topology
	"""
	CoreSwitchList = []
	AggSwitchList = []
	EdgeSwitchList = []
	HostList = []

	def __init__(self, k, density):
		self.pod = k
		self.density = density
		self.iCoreLayerSwitch = (k/2)**2
		self.iAggLayerSwitch = k*k/2
		self.iEdgeLayerSwitch = k*k/2
		self.iHost = self.iEdgeLayerSwitch * density

		# Topo initiation
		Topo.__init__(self)

	def createNodes(self):
		self.createCoreLayerSwitch(self.iCoreLayerSwitch)
		self.createAggLayerSwitch(self.iAggLayerSwitch)
		self.createEdgeLayerSwitch(self.iEdgeLayerSwitch)
		self.createHost(self.iHost)

	def _addSwitch(self, number, level, switch_list):
		"""
			Create switches
		"""
		for i in xrange(1, number+1):
			PREFIX = str(level) + "00"
			if i >= 10:
				PREFIX = str(level) + "0"
			switch_list.append(self.addSwitch(PREFIX + str(i)))

	def createCoreLayerSwitch(self, NUMBER):
		self._addSwitch(NUMBER, 1, self.CoreSwitchList)

	def createAggLayerSwitch(self, NUMBER):
		self._addSwitch(NUMBER, 2, self.AggSwitchList)

	def createEdgeLayerSwitch(self, NUMBER):
		self._addSwitch(NUMBER, 3, self.EdgeSwitchList)

	def createHost(self, NUMBER):
		"""
			Create hosts
		"""
		for i in xrange(1, NUMBER+1):
			if i >= 100:
				PREFIX = "h"
			elif i >= 10:
				PREFIX = "h0"
			else:
				PREFIX = "h00"
			self.HostList.append(self.addHost(PREFIX + str(i)))

	def createLinks(self, bw_c2a=10, bw_a2e=10, bw_e2h=10):
		# Core to Agg
		end = self.pod/2
		for x in xrange(0, self.iAggLayerSwitch, end):
			for i in xrange(0, end):
				for j in xrange(0, end):
					self.addLink(
						self.CoreSwitchList[i*end+j],
						self.AggSwitchList[x+i],
						bw=bw_c2a, max_queue_size=1000)   # use_htb=False

		# Agg to Edge
		for x in xrange(0, self.iAggLayerSwitch, end):
			for i in xrange(0, end):
				for j in xrange(0, end):
					self.addLink(
						self.AggSwitchList[x+i], self.EdgeSwitchList[x+j],
						bw=bw_a2e, max_queue_size=1000)   # use_htb=False

		# Edge to Host
		for x in xrange(0, self.iEdgeLayerSwitch):
			for i in xrange(0, self.density):
				self.addLink(
					self.EdgeSwitchList[x],
					self.HostList[self.density * x + i],
					bw=bw_e2h, max_queue_size=1000)   # use_htb=False

	def set_ovs_protocol_13(self,):
		"""
			Set the OpenFlow version for switches
		"""
		self._set_ovs_protocol_13(self.CoreSwitchList)
		self._set_ovs_protocol_13(self.AggSwitchList)
		self._set_ovs_protocol_13(self.EdgeSwitchList)

	def _set_ovs_protocol_13(self, sw_list):
		for sw in sw_list:
			cmd = "sudo ovs-vsctl set bridge %s protocols=OpenFlow13" % sw
			os.system(cmd)


def set_host_ip(net, topo):
	hostlist = []
	for k in xrange(len(topo.HostList)):
		hostlist.append(net.get(topo.HostList[k]))
	i = 1
	j = 1
	for host in hostlist:
		host.setIP("10.%d.0.%d" % (i, j))
		j += 1
		if j == topo.density+1:
			j = 1
			i += 1

def create_subnetList(topo, num):
	"""
		Create the subnet list of the certain Pod
	"""
	subnetList = []
	remainder = num % (topo.pod/2)
	if topo.pod == 4:
		if remainder == 0:
			subnetList = [num-1, num]
		elif remainder == 1:
			subnetList = [num, num+1]
		else:
			pass
	elif topo.pod == 8:
		if remainder == 0:
			subnetList = [num-3, num-2, num-1, num]
		elif remainder == 1:
			subnetList = [num, num+1, num+2, num+3]
		elif remainder == 2:
			subnetList = [num-1, num, num+1, num+2]
		elif remainder == 3:
			subnetList = [num-2, num-1, num, num+1]
		else:
			pass
	else:
		pass
	return subnetList

def install_proactive(net, topo):
	"""
		Install proactive flow entries for switches
	"""
	# Edge Switch
	for sw in topo.EdgeSwitchList:
		num = int(sw[-2:])

		# Downstream
		for i in xrange(1, topo.density+1):
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=40,arp, \
				nw_dst=10.%d.0.%d,actions=output:%d'" % (sw, num, i, topo.pod/2+i)
			os.system(cmd)
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=40,ip, \
				nw_dst=10.%d.0.%d,actions=output:%d'" % (sw, num, i, topo.pod/2+i)
			os.system(cmd)

		# Upstream
		if topo.pod == 4:
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
					'table=0,idle_timeout=0,hard_timeout=0,priority=40,arp, \
					nw_src=10.%d.0.1,actions=output:1'" % (sw, num)
			os.system(cmd)
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=40,ip, \
				nw_src=10.%d.0.1,actions=output:1'" % (sw, num)
			os.system(cmd)
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=40,arp, \
				nw_src=10.%d.0.2,actions=output:2'" % (sw, num)
			os.system(cmd)
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=40,ip, \
				nw_src=10.%d.0.2,actions=output:2'" % (sw, num)
			os.system(cmd)
			# cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
			# 'group_id=1,type=select,bucket=output:1,bucket=output:2'" % sw
		elif topo.pod == 8:
			cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
			'group_id=1,type=select,bucket=output:1,bucket=output:2,\
			bucket=output:3,bucket=output:4'" % sw
		else:
			pass
		# os.system(cmd)
		# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
		# 'table=0,priority=10,arp,actions=group:1'" % sw
		# os.system(cmd)
		# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
		# 'table=0,priority=10,ip,actions=group:1'" % sw
		# os.system(cmd)

	# Aggregate Switch
	for sw in topo.AggSwitchList:
		num = int(sw[-2:])
		subnetList = create_subnetList(topo, num)

		# Downstream
		k = 1
		for i in subnetList:
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=40,arp, \
				nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, topo.pod/2+k)
			os.system(cmd)
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=40,ip, \
				nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, topo.pod/2+k)
			os.system(cmd)
			k += 1

		# Upstream
		if topo.pod == 4:
			for i in xrange(0, 2):
				cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
					'table=0,idle_timeout=0,hard_timeout=0,priority=40,arp, \
					nw_src=10.%d.0.1,actions=output:1'" % (sw, num)
				os.system(cmd)
				cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
					'table=0,idle_timeout=0,hard_timeout=0,priority=40,ip, \
					nw_src=10.%d.0.1,actions=output:1'" % (sw, num)
				os.system(cmd)
				cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
					'table=0,idle_timeout=0,hard_timeout=0,priority=40,arp, \
					nw_src=10.%d.0.2,actions=output:2'" % (sw, num)
				os.system(cmd)
				cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
					'table=0,idle_timeout=0,hard_timeout=0,priority=40,ip, \
					nw_src=10.%d.0.2,actions=output:2'" % (sw, num)
				os.system(cmd)
				if num % 2 == 1:
					num = num + 1
				else:
					num = num - 1
			# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
			# 	'table=0,idle_timeout=0,hard_timeout=0,priority=40,arp, \
			# 	nw_src=10.%d.0.1,actions=output:1'" % (sw, num)
			# os.system(cmd)
			# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
			# 	'table=0,idle_timeout=0,hard_timeout=0,priority=40,ip, \
			# 	nw_src=10.%d.0.1,actions=output:1'" % (sw, num)
			# os.system(cmd)
			# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
			# 	'table=0,idle_timeout=0,hard_timeout=0,priority=40,arp, \
			# 	nw_src=10.%d.0.2,actions=output:2'" % (sw, num)
			# os.system(cmd)
			# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
			# 	'table=0,idle_timeout=0,hard_timeout=0,priority=40,ip, \
			# 	nw_src=10.%d.0.2,actions=output:2'" % (sw, num)
			# os.system(cmd)
			# cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
			# 'group_id=1,type=select,bucket=output:1,bucket=output:2'" % sw
		elif topo.pod == 8:
			cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
			'group_id=1,type=select,bucket=output:1,bucket=output:2,\
			bucket=output:3,bucket=output:4'" % sw
		else:
			pass
		# os.system(cmd)
		# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
		# 'table=0,priority=10,arp,actions=group:1'" % sw
		# os.system(cmd)
		# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
		# 'table=0,priority=10,ip,actions=group:1'" % sw
		# os.system(cmd)

	# Core Switch
	for sw in topo.CoreSwitchList:
		j = 1
		k = 1
		for i in xrange(1, len(topo.EdgeSwitchList)+1):
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=10,arp, \
				nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, j)
			os.system(cmd)
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=10,ip, \
				nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, j)
			os.system(cmd)
			k += 1
			if k == topo.pod/2 + 1:
				j += 1
				k = 1

def create_hostlist(host_numbers):
	"""
		Create hosts list
	"""
	hostlist = []
	for i in xrange(1, host_numbers+1):
		if i >= 100:
			PREFIX = "h"
		elif i >= 10:
			PREFIX = "h0"
		else:
			PREFIX = "h00"
		hostlist.append(PREFIX + str(i))
	return hostlist

def monitor_devs_ng(fname="./txrate.txt", interval_sec=0.1):
	"""
		Use the bwm-ng to monitor network and collect datas
	"""
	cmd = "sleep 1; bwm-ng -t %s -o csv -u bits -T rate -C ',' > %s" %  (interval_sec * 1000, fname)
	Popen(cmd, shell=True).wait()

def traffic_generation(net, topo, times, flowPeers, traffic):
	"""
		Generate traffic
	"""
	# Start the servers
	serversList = set([peer[1] for peer in flowPeers])
	for server in serversList:
		path = "./results/" + traffic + "/hash/" + server + ".txt"
		server = net.get(server)
		server.cmd("iperf -s -i 1 > %s &" % (path))

	time.sleep(3)

	# Start the clients
	for src, dest in flowPeers:
		# path = "./results/ecmps/" + src + ".txt"
		server = net.get(dest)
		client = net.get(src)
		client.cmd("iperf -c %s -t %d -i 1 > /dev/null &" % (server.IP(), 120))
		time.sleep(2)

	# Wait for the traffic to become stable
	time.sleep(10)

	file_names = './results/' + traffic + '/hash/bwmng.txt'
	monitor = Process(target=monitor_devs_ng, args=(file_names, 1.0))
	monitor.start()

	time.sleep(times + 5)

	monitor.terminate()
	os.system('killall bwm-ng')
	os.system('killall iperf')

def createTopo(pod, density, host_numbers, flow_numbers, bw_c2a=10, bw_a2e=10, bw_e2h=10):
	"""
		Create topology
	"""
	# Create Topo
	topo = Fattree(pod, density)
	topo.createNodes()
	topo.createLinks(bw_c2a=bw_c2a, bw_a2e=bw_a2e, bw_e2h=bw_e2h)

	net = Mininet(topo=topo, link=TCLink, controller=None, autoSetMacs=True)
	net.start()

	# topo.set_ovs_protocol_13()
	set_host_ip(net, topo)
	install_proactive(net, topo)

	time.sleep(5)

	# Generate traffics and test the performance of the network
	traffic_generation(net, topo, 60, randoms.peers1, 'random')
	# traffic_generation(net, topo, 60, stag_01_02.peers1, 'stag_0.1_0.2')
	# traffic_generation(net, topo, 60, stag_02_03.peers1, 'stag_0.2_0.3')
	# traffic_generation(net, topo, 60, stag_03_03.peers1, 'stag_0.3_0.3')
	# traffic_generation(net, topo, 60, stag_04_03.peers1, 'stag_0.4_0.3')
	# traffic_generation(net, topo, 60, stride_1.peers1, 'stride1')
	# traffic_generation(net, topo, 60, stride_2.peers1, 'stride2')
	# traffic_generation(net, topo, 60, stride_4.peers1, 'stride4')
	# traffic_generation(net, topo, 60, stride_8.peers1, 'stride8')
	# traffic_generation(net, topo, 60, hotspot.peers1, 'hotspot')

	# CLI(net)
	net.stop()

if __name__ == '__main__':
	setLogLevel('info')
	host_numbers = 16
	flow_numbers = 1
	if os.getuid() != 0:
		logging.warning("You are NOT root!")
	elif os.getuid() == 0:
		createTopo(4, 2, host_numbers, flow_numbers)
