import argparse
import random


parser = argparse.ArgumentParser(description="BFlows experiments")
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
	return peers

def create_random_peers(HostList, flows_num_per_host):
	"""
		Create random iperf peers to generate traffic.
	"""
	peers = []
	for host in HostList:
		for i in xrange(flows_num_per_host):
			peer = random.choice(HostList)
			while (peer == host or (host, peer) in peers):
				peer = random.choice(HostList)
			peers.append((host, peer))
	return peers

def create_stride_peers(HostList, flows_num_per_host, host_num, number):
	"""
		Create stride iperf peers to generate traffic.
	"""
	peers = []
	num = 0
	for host in HostList:
		for i in xrange(flows_num_per_host):
			peer_num = (num + number) % host_num
			peer = HostList[peer_num]
			peers.append((host, peer))
		num = num + 1
	return peers

def create_hotspot_peers(HostList, flows_num_per_host, host_num, number):
	"""
		Create hotspot iperf peers to generate traffic.
	"""
	peers = []
	hotspot_host = []

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

def create_peers():
	"""
		Create iperf host peers and write to a file.
	"""
	host_num = args.k ** 3 /4
	HostList = create_hostlist(host_num)
	traffics = ['randoms', 'stag_0.1_0.2', 'stag_0.2_0.3', 'stag_0.3_0.3', 'stag_0.4_0.3', 'stride_1', 'stride_2',
				'stride_4', 'stride_8', 'hotspot']

	for i in range(len(traffics)):
		if traffics[i].startswith('stag'):
			number = 1
			traffics_prob = traffics[i].split('_')
			edge_prob = float(traffics_prob[1])
			pod_prob = float(traffics_prob[2])
			file_name = './peers/stag_0' + str(int(edge_prob * 10)) + '_0' + str(int(pod_prob * 10)) + '.py'
			file_save = open(file_name, 'w')
			# while number <= 10:
			flows_peers = create_stag_peers(HostList, edge_prob, pod_prob, args.flows_num_per_host)

			# Shuffle the sequence of the flows_peers.
			random.shuffle(flows_peers)

			# Write flows_peers into a file for reuse.
			file_save.write('peers' + str(number) + '=%s\n' % flows_peers)
			# number = number + 1
			file_save.close()
		elif traffics[i].startswith('stride'):
			number = 1
			numbers = traffics[i].split('_')[1]
			file_name = './peers/' + traffics[i] + '.py'
			file_save = open(file_name, 'w')
			flows_peers = create_stride_peers(HostList, args.flows_num_per_host, host_num, int(numbers))

			random.shuffle(flows_peers)

			file_save.write('peers' + str(number) + '=%s\n' % flows_peers)
			file_save.close()
		elif traffics[i].startswith('hotspot'):
			number = 1
			numbers = host_num / 8
			file_name = './peers/' + traffics[i] + '.py'
			file_save = open(file_name, 'w')
			flows_peers = create_hotspot_peers(HostList, args.flows_num_per_host, host_num, numbers)

			random.shuffle(flows_peers)

			file_save.write('peers' + str(number) + '=%s\n' % flows_peers)
			file_save.close()
		else:
			number = 1
			file_name = './peers/' + traffics[i] + '.py'
			file_save = open(file_name, 'w')
			# while number <= 10:
			flows_peers = create_random_peers(HostList, args.flows_num_per_host)

			# Shuffle the sequence of the flows_peers.
			random.shuffle(flows_peers)

			# Write flows_peers into a file for reuse.
			file_save.write('peers' + str(number) + '=%s\n' % flows_peers)
			# number = number + 1
			file_save.close()

if __name__ == '__main__':
	create_peers()
