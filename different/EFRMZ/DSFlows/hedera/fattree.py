from mininet.net import Mininet
from mininet.node import Controller, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel
from mininet.link import Link, Intf, TCLink
from mininet.topo import Topo

import os
import logging
import argparse
import time
import signal
from subprocess import Popen
from multiprocessing import Process

import sys
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
import peers


parser = argparse.ArgumentParser(description="Parameters importation")
parser.add_argument('--k', dest='k', type=int, default=4, choices=[4, 8], help="Switch fanout number")
parser.add_argument('--duration', dest='duration', type=int, default=60, help="Duration (sec) for each iperf traffic generation")
parser.add_argument('--dir', dest='output_dir', help="Directory to store outputs")
parser.add_argument('--cpu', dest='cpu', type=float, default=1.0, help='Total CPU to allocate to hosts')
args = parser.parse_args()


class Fattree(Topo):
	"""
		Class of Fattree Topology.
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
			Create switches.
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
			Create hosts.
		"""
		for i in xrange(1, NUMBER+1):
			if i >= 100:
				PREFIX = "h"
			elif i >= 10:
				PREFIX = "h0"
			else:
				PREFIX = "h00"
			self.HostList.append(self.addHost(PREFIX + str(i), cpu=args.cpu/float(NUMBER)))

	def createLinks(self, bw_c2a=10, bw_a2e=10, bw_e2h=10):
		"""
			Add network links.
		"""
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
			Set the OpenFlow version for switches.
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
		Create the subnet list of the certain Pod.
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
		Install proactive flow entries for switches.
	"""
	bw_sensitive_port_list = [5001]
	# Edge Switch
	for sw in topo.EdgeSwitchList:
		num = int(sw[-2:])

		# Downstream
		for i in xrange(1, topo.density+1):
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=30,arp, \
				nw_dst=10.%d.0.%d,actions=output:%d'" % (sw, num, i, topo.pod/2+i)
			os.system(cmd)
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=30,ip, \
				nw_dst=10.%d.0.%d,actions=output:%d'" % (sw, num, i, topo.pod/2+i)
			os.system(cmd)

		# Upstream
		# Install group entries.
		if topo.pod == 4:
			cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
			'group_id=1,type=select,bucket=output:1,bucket=output:2'" % sw
		elif topo.pod == 8:
			cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
			'group_id=1,type=select,bucket=output:1,bucket=output:2,\
			bucket=output:3,bucket=output:4'" % sw
		else:
			pass
		os.system(cmd)
		
		# Flow table
		# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
		# 'table=0,priority=10,arp,actions=group:1'" % (sw)
		# os.system(cmd)
		# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
		# 'table=0,priority=10,ip,actions=group:1'" % (sw)
		# os.system(cmd)

		# Install bandwidth-sensitive service flow entry.
		for port in bw_sensitive_port_list:
			# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
			# 	'table=0,idle_timeout=0,hard_timeout=0,priority=20,tcp, \
			# 	tcp_src=%d,actions=output:CONTROLLER'" % (sw, port)
			# os.system(cmd)
			# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
			# 	'table=0,idle_timeout=0,hard_timeout=0,priority=20,tcp, \
			# 	tcp_dst=%d,actions=output:CONTROLLER'" % (sw, port)
			# os.system(cmd)
			# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
			# 	'table=0,idle_timeout=0,hard_timeout=0,priority=20,udp, \
			# 	udp_src=%d,actions=output:CONTROLLER'" % (sw, port)
			# os.system(cmd)
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=20,udp, \
				udp_dst=%d,actions=output:CONTROLLER'" % (sw, port)
			os.system(cmd)

	# Aggregate Switch
	for sw in topo.AggSwitchList:
		num = int(sw[-2:])
		subnetList = create_subnetList(topo, num)

		# Downstream
		k = 1
		for i in subnetList:
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=10,arp, \
				nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, topo.pod/2+k)
			os.system(cmd)
			cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
				'table=0,idle_timeout=0,hard_timeout=0,priority=10,ip, \
				nw_dst=10.%d.0.0/16, actions=output:%d'" % (sw, i, topo.pod/2+k)
			os.system(cmd)
			k += 1

		# Upstream
		if topo.pod == 4:
			cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
			'group_id=1,type=select,bucket=output:1,bucket=output:2'" % sw
		elif topo.pod == 8:
			cmd = "ovs-ofctl add-group %s -O OpenFlow13 \
			'group_id=1,type=select,bucket=output:1,bucket=output:2,\
			bucket=output:3,bucket=output:4'" % sw
		else:
			pass
		# os.system(cmd)
		# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
		# 'table=0,priority=10,arp,actions=group:1'" % (sw)
		# os.system(cmd)
		# cmd = "ovs-ofctl add-flow %s -O OpenFlow13 \
		# 'table=0,priority=10,ip,actions=group:1'" % (sw)
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

def monitor_devs_ng(fname="./txrate.txt", interval_sec=0.1):
	"""
		Use bwm-ng tool to collect interface transmit rate statistics.
		bwm-ng Mode: rate;
		interval time: 1s.
	"""
	cmd = "sleep 1; bwm-ng -t %s -o csv -u bits -T rate -C ',' > %s" %  (interval_sec * 1000, fname)
	Popen(cmd, shell=True).wait()

def traffic_generation(net, topo, flows_peers):
	"""
		Generate traffics and test the performance of the network.
	"""
	# 1. Start iperf. (Elephant flows)
	# Start the servers.
	elephant_flows = []
	mice_flows = []
	number = 14
	output_dir = "../data/hedera/9/5/"

	it = 0
	for src, dest in flows_peers:
		if it < number:
			elephant_flows.append((src, dest))
		else:
			mice_flows.append((src, dest))
		it = it + 1

	serversList = set([peer[1] for peer in elephant_flows])
	for server in serversList:
		path = output_dir + server + ".txt"
		server = net.get(server)
		server.cmd("iperf -s -u > %s &" % (path))

	time.sleep(3)

	# Start the clients.
	i = 0
	j = 0
	for src, dest in elephant_flows:
		server = net.get(dest)
		client = net.get(src)
		# filename = src[1:]
		# client.cmd("iperf -c %s -t %d > %s/%s &" % (server.IP(), args.duration, args.output_dir, 'client'+filename+'.txt'))
		client.cmd("iperf -c %s -b 6M -t %d > /dev/null &" % (server.IP(), 1990))   # Its statistics is useless, just throw away. 1990 just means a great number.
		time.sleep(3)
		if j < 10:
			for k in xrange(2):
				p = mice_flows[i]
				src = p[0]
				dest = p[1]
				client = net.get(src)
				server = net.get(dest)
				client.cmd("ping -c %d -i 0.1 -n -q %s >> %s/%s &" % (200, server.IP(), output_dir, 'successive_packets.txt'))
				time.sleep(1)
				i = i + 1
		else:
			for k in xrange(3):
				p = mice_flows[i]
				src = p[0]
				dest = p[1]
				client = net.get(src)
				server = net.get(dest)
				client.cmd("ping -c %d -i 0.1 -n -q %s >> %s/%s &" % (200, server.IP(), output_dir, 'successive_packets.txt'))
				i = i + 1
			time.sleep(2)
		j = j + 1

	# Wait for the traffic to become stable.
	# time.sleep(10)

	# # 2. Start bwm-ng to monitor throughput.
	# monitor = Process(target = monitor_devs_ng, args = ('%s/bwmng.txt' % args.output_dir, 1.0))
	# monitor.start()

	# 3. Start ping. (Mouse flows)

	# Successive packets.
	# for src, dest in mice_flows:
	# 	client = net.get(src)
	# 	server = net.get(dest)
	# 	client.cmd("ping -c %d -i 0.1 -n -q %s >> %s/%s &" % (60, server.IP(), output_dir, 'successive_packets.txt'))

	# 4. The experiment is going on.
	time.sleep(65)

	# 5. Shut down.
	# monitor.terminate()
	# os.system('killall bwm-ng')
	os.system('killall iperf')
	time.sleep(6)

def run_experiment(pod, density, ip="127.0.0.1", port=6661, bw_c2a=10, bw_a2e=10, bw_e2h=10):
	"""
		Firstly, start up Mininet;
		secondly, start up Ryu controller;
		thirdly, generate traffics and test the performance of the network.
	"""
	# Create Topo.
	topo = Fattree(pod, density)
	topo.createNodes()
	topo.createLinks(bw_c2a=bw_c2a, bw_a2e=bw_a2e, bw_e2h=bw_e2h)

	# 1. Start Mininet.
	CONTROLLER_IP = ip
	CONTROLLER_PORT = port
	net = Mininet(topo=topo, link=TCLink, controller=None, autoSetMacs=True)
	net.addController(
		'controller', controller=RemoteController,
		ip=CONTROLLER_IP, port=CONTROLLER_PORT)
	net.start()

	# Set the OpenFlow version for switches as 1.3.0.
	# topo.set_ovs_protocol_13()
	# Set the IP addresses for hosts.
	set_host_ip(net, topo)
	# Install proactive flow entries.
	install_proactive(net, topo)

	# Wait until the controller has discovered network topology.
	time.sleep(20)

	# 3. Generate traffics and test the performance of the network.
	traffic_generation(net, topo, peers.peers5)

	# CLI(net)
	net.stop()

if __name__ == '__main__':
	setLogLevel('info')
	if os.getuid() != 0:
		logging.warning("You are NOT root!")
	elif os.getuid() == 0:
		# run_experiment(4, 2) or run_experiment(8, 4)
		run_experiment(4, 2)
