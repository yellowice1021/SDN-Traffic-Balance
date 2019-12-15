# Copyright (C) 2016 Huang MaChi at Chongqing University
# of Posts and Telecommunications, Chongqing, China.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import argparse
import random


parser = argparse.ArgumentParser(description="EFattree experiments")
parser.add_argument('--k', dest='k', type=int, default=4, choices=[4, 8], help="Switch fanout number")
parser.add_argument('--traffic', dest='traffic', default="stag_0.2_0.3", help="Traffic pattern to simulate")
parser.add_argument('--fnum', dest='flows_num_per_host', type=int, default=1, help="Number of iperf flows per host")
args = parser.parse_args()


def create_subnetList(num):
	"""
		Create the subnet list of the certain Pod.
	"""
	subnetList = []
	remainder = num % (args.k / 2)
	if args.k == 4:
		if remainder == 0:
			subnetList = [num-1, num]
		elif remainder == 1:
			subnetList = [num, num+1]
		else:
			pass
	elif args.k == 8:
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

def create_swList(num):
	"""
		Create the host list under the certain Edge switch.
		Note: Part of this function is the same with the create_subnetList( ).
	"""
	swList = []
	list_num = create_subnetList(num)
	for i in list_num:
		if i < 10:
			swList.append('h00' + str(i))
		elif i < 100:
			swList.append('h0' + str(i))
		else:
			swList.append('h' + str(i))
	return swList

def create_podList(num):
	"""
		Create the host list of the certain Pod.
	"""
	podList = []
	list_num = []
	host_num_per_pod = args.k ** 2 / 4
	quotient = (num - 1) / host_num_per_pod
	list_num = [i for i in range(host_num_per_pod * quotient + 1, host_num_per_pod * quotient + host_num_per_pod + 1)]

	for i in list_num:
		if i < 10:
			podList.append('h00' + str(i))
		elif i < 100:
			podList.append('h0' + str(i))
		else:
			podList.append('h' + str(i))
	return podList

def create_stag_peers(HostList, edge_prob, pod_prob, flows_num_per_host):
	"""
		Create staggered iperf peers to generate traffic.
	"""
	peers = []
	peers_first = []
	for host in HostList:
		num = int(host[1:])
		swList = create_swList(num)
		podList = create_podList(num)
		new_peers = []
		while len(new_peers) < flows_num_per_host:
			probability = random.random()
			if probability < edge_prob:
				peer = random.choice(swList)
				if (peer != host) and ((host, peer) not in new_peers):
					new_peers.append((host, peer))
			elif edge_prob <= probability < edge_prob + pod_prob:
				peer = random.choice(podList)
				if (peer not in swList) and ((host, peer) not in new_peers):
					new_peers.append((host, peer))
			else:
				peer = random.choice(HostList)
				if (peer not in podList) and ((host, peer) not in new_peers):
					new_peers.append((host, peer))
		peers.extend(new_peers)
	random.shuffle(peers)
	for host in HostList:
		num = int(host[1:])
		swList = create_swList(num)
		podList = create_podList(num)
		new_peers = []
		while len(new_peers) < flows_num_per_host:
			probability = random.random()
			if probability < edge_prob:
				peer = random.choice(swList)
				if (peer != host) and ((host, peer) not in new_peers):
					new_peers.append((host, peer))
			elif edge_prob <= probability < edge_prob + pod_prob:
				peer = random.choice(podList)
				if (peer not in swList) and ((host, peer) not in new_peers):
					new_peers.append((host, peer))
			else:
				peer = random.choice(HostList)
				if (peer not in podList) and ((host, peer) not in new_peers):
					new_peers.append((host, peer))
		peers_first.extend(new_peers)
	random.shuffle(peers_first)
	for host in peers_first:
		peers.append(host)
	return peers

def create_stride_peers(HostList, flow_num, stride_num):
	"""
		Create stride iperf peers to generate traffic
	"""
	peers = []
	peers_first = []
	for host in HostList:
		for i in xrange(flow_num):
			peers_number = (HostList.index(host) + stride_num) % 16
			peer = HostList[peers_number]
			peers.append((host, peer))

	random.shuffle(peers)

	for host in HostList:
		for i in xrange(flow_num):
			peers_number = (HostList.index(host) + stride_num) % 16
			peer = HostList[peers_number]
			peers_first.append((host, peer))

	random.shuffle(peers_first)

	for host in peers_first:
		peers.append(host)

	return peers

def create_random_peers(HostList, flow_num):
	"""
		Create random iperf peers to generate traffic.
	"""
	peers = []
	peers_first = []
	for host in HostList:
		for i in xrange(flow_num):
			peer = random.choice(HostList)
			while (peer == host) or (host, peer) in peers:
				peer = random.choice(HostList)
			peers.append((host, peer))

	random.shuffle(peers)

	for host in HostList:
		for i in xrange(flow_num):
			peer = random.choice(HostList)
			while (peer == host) or (host, peer) in peers_first:
				peer = random.choice(HostList)
			peers_first.append((host, peer))

	random.shuffle(peers_first)

	for host in peers_first:
		peers.append(host)

	return peers

def create_hotspot_peers(HostList, flows_num_per_host, number):
	"""
		Create hotspot iperf peers to generate traffic.
	"""
	peers = []
	hotspot_host = []
	peers_first = []
	hotspot_host_first = []

	for i in xrange(number):
		hotspot = random.choice(HostList)
		while(hotspot in hotspot_host):
			hotspot = random.choice(HostList)
		hotspot_host.append(hotspot)

	for host in HostList:
		for i in xrange(flows_num_per_host):
			peer = random.choice(hotspot_host)
			while(peer == host):
				peer = random.choice(hotspot_host)
			peers.append((host, peer))

	random.shuffle(peers)

	for i in xrange(number):
		hotspot = random.choice(HostList)
		while(hotspot in hotspot_host_first):
			hotspot = random.choice(HostList)
		hotspot_host_first.append(hotspot)

	for host in HostList:
		for i in xrange(flows_num_per_host):
			peer = random.choice(hotspot_host)
			while(peer == host):
				peer = random.choice(hotspot_host)
			peers_first.append((host, peer))

	random.shuffle(peers_first)

	for host in peers_first:
		peers.append(host)

	return peers

def create_hostlist(num):
	"""
		Create hosts list.
	"""
	hostlist = []
	for i in xrange(1, num+1):
		if i >= 100:
			PREFIX = "h"
		elif i >= 10:
			PREFIX = "h0"
		else:
			PREFIX = "h00"
		hostlist.append(PREFIX + str(i))
	return hostlist

def create_peers(host_num, flow_num):
	"""
		Create iperf host peers and write to a file.
	"""
	HostList = create_hostlist(host_num)

	# peers = create_random_peers(HostList, flow_num)
	# # random.shuffle(peers)
	# file_save = open('peers.py', 'w')
	# file_save.write('peers=%s' % peers)
	# file_save.close()

	# hotspot_number = host_num / 4
	# peers = create_hotspot_peers(HostList, flow_num, hotspot_number)
	# # random.shuffle(peers)
	# file_save = open('hotspot.py', 'w')
	# file_save.write('peers=%s' % peers)
	# file_save.close()

	# peers = create_stride_peers(HostList, flow_num, 1)
	# file_save = open('stride1.py', 'w')
	# file_save.write('peers=%s' % peers)
	# file_save.close()

	# peers = create_stride_peers(HostList, flow_num, 2)
	# file_save = open('stride2.py', 'w')
	# file_save.write('peers=%s' % peers)
	# file_save.close()

	# peers = create_stride_peers(HostList, flow_num, 4)
	# file_save = open('stride4.py', 'w')
	# file_save.write('peers=%s' % peers)
	# file_save.close()

	# peers = create_stride_peers(HostList, flow_num, 4)
	# file_save = open('stride8.py', 'w')
	# file_save.write('peers=%s' % peers)
	# file_save.close()

	# peers = create_stag_peers(HostList, 0.2, 0.3, flow_num)
	# file_save = open('stag2.py', 'w')
	# file_save.write('peers=%s' % peers)
	# file_save.close()

	# peers = create_stag_peers(HostList, 0.5, 0.3, flow_num)
	# file_save = open('stag5.py', 'w')
	# file_save.write('peers=%s' % peers)
	# file_save.close()

	peers = create_stag_peers(HostList, 0.7, 0.2, flow_num)
	file_save = open('stag7.py', 'w')
	file_save.write('peers=%s' % peers)
	file_save.close()

if __name__ == '__main__':
	host_num = 16
	flow_num = 1
	create_peers(host_num, flow_num)
