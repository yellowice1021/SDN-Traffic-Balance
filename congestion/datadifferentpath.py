import re
import matplotlib.pyplot as plt
import numpy as np


def read_file_network_stastics(file_name, delim=','):
	"""
		Read the bwmng file
	"""
	read_file = open(file_name, 'r')
	lines = read_file.xreadlines()
	lines_list = []
	for line in lines:
		line_list = line.strip().split(delim)
		lines_list.append(line_list)
	read_file.close()

	# Remove the last second's statistics, because they are mostly not intact.
	last_second = lines_list[-1][0]
	_lines_list = lines_list[:]
	for line in _lines_list:
		if line[0] == last_second:
			lines_list.remove(line)

	return lines_list

def read_file_network_delay(file_name):
	"""
		Read the ping file
	"""
	read_file = open(file_name, 'r')
	lines = read_file.xreadlines()
	lines_list = []
	for line in lines:
		if line.endswith(' ms\n') and not line.startswith('rtt'):
			lines_list.append(line)
	read_file.close()
	return lines_list

def get_total_throughout(total_throughout):
	"""
		Get total throughout
	"""
	lines_list = read_file_network_stastics('./results/differentpath/bwmng.txt')
	first_second = int(lines_list[0][0])
	column_bytes_out = 6   # bytes_out
	switch = 's2'
	sw = re.compile(switch)
	realtime_throught = {}

	for i in xrange(121):
		if not total_throughout.has_key(i):
			total_throughout[i] = 0

	for i in xrange(121):
		if not realtime_throught.has_key(i):
			realtime_throught[i] = 0

	for row in lines_list:
		iface_name = row[1]
		if sw.match(iface_name):
			if int(iface_name[-1]) <= 3:   # Choose host-connecting interfaces only.
				if (int(row[0]) - first_second) <= 120:   # Take the good values only.
					realtime_throught[int(row[0]) - first_second] += float(row[column_bytes_out]) * 8.0 / (10 ** 6)   # Mbit

	for i in xrange(121):
		for j in xrange(i+1):
			total_throughout[i] += realtime_throught[j]   # Mbit

	return total_throughout

def get_value_list_throughout(value_dict):
	"""
		Get the values from the throughout data structure
	"""
	value_list = []
	for i in xrange(121):
		value_list.append(value_dict[i])
	return value_list

def get_value_list_delay(value_dict, time):
	"""
		Get the values from the RRT data structure
	"""
	value_list = [0]
	sequence_list = [0]
	for i in xrange(time + 1):
		if value_dict[i] != 0:
			sequence_list.append(i)
			value_list.append(value_dict[i])
	return sequence_list, value_list

def get_value_list_loss(value_dict, sequence):
	"""
		Get the packet loss values
	"""
	num = 0
	for i in xrange(sequence, sequence + 30):
		if i != 0:
			if value_dict[i] == 0:
				num += 1
	rate = num / 30.0
	return rate

def get_realtime_speed(switch):
	"""
		Get realtime speed of individual flow
	"""
	realtime_speed = {}
	lines_list = read_file_network_stastics('./results/differentpath/bwmng.txt')
	first_second = int(lines_list[0][0])
	column_bytes_out_rate = 2   # bytes_out/s
	sw = re.compile(switch)

	for i in xrange(121):
		if not realtime_speed.has_key(i):
			realtime_speed[i] = 0

	for row in lines_list:
		iface_name = row[1]
		if sw.match(iface_name):
			if (int(row[0]) - first_second) <= 120:   # Take the good values only.
				realtime_speed[int(row[0]) - first_second] += float(row[column_bytes_out_rate]) * 8.0 / (10 ** 6)   # Mbit/s

	return realtime_speed

def get_delay_values(delay_dict):
	"""
		Get rtt of ping traffic
	"""
	lines_list = read_file_network_delay('./results/differentpath/ping.txt')
	for i in xrange(121):
		if not delay_dict.has_key(i):
			delay_dict[i] = 0

	for row in lines_list:
		sequence = int(row.split(' ')[4].split('=')[1])
		delay = float(row.split(' ')[6].split('=')[1])
		delay_dict[sequence] = delay

	return delay_dict

def plot_delay(roundtrip_delay):
	"""
		Plot the delay of ping traffic
	"""
	# plot the delay
	fig = plt.figure()
	fig.set_size_inches(12, 6)
	x, y = get_value_list_delay(roundtrip_delay, 120)
	plt.plot(x, y, 'g-', linewidth=2)
	plt.xlabel('Time (s)', fontsize='x-large')
	plt.xlim(0, 120)
	plt.xticks(np.arange(0, 121, 30))
	plt.ylabel('RTT of Ping Traffic\n(ms)', fontsize='x-large')
	plt.grid(True)
	plt.savefig('./results/differentpath/delay.png')

	# # ploy the delay between 0 and 60s
	# fig = plt.figure()
	# fig.set_size_inches(12, 6)
	# x, y = get_value_list_delay(roundtrip_delay, 60)
	# plt.plot(x, y, 'g-', linewidth=2)
	# plt.xlabel('Time (s)', fontsize='x-large')
	# plt.xlim(0, 60)
	# plt.xticks(np.arange(0, 61, 30))
	# plt.ylabel('RTT of Ping Traffic\n(ms)', fontsize='x-large')
	# plt.grid(True)
	# plt.savefig('./results/delaysecond.png')


def plot_packet_loss(roundtrip_delay):
	"""
		Plot packet loss of ping traffic
	"""
	fig = plt.figure()
	fig.set_size_inches(12, 6)
	num_groups = 1
	first_thirty = get_value_list_loss(roundtrip_delay, 0)
	second_thirty = get_value_list_loss(roundtrip_delay, 30)
	third_thirty = get_value_list_loss(roundtrip_delay, 60)
	fourth_thirty = get_value_list_loss(roundtrip_delay, 90)
	index = np.arange(num_groups)
	bar_width = 30
	plt.bar(index, first_thirty, bar_width, color='b', label='0-30s', alpha=0.8)
	plt.bar(index + 1 * bar_width, second_thirty, bar_width, color='g', label='30-60s', alpha=0.8)
	plt.bar(index + 2 * bar_width, third_thirty, bar_width, color='r', label='60-90s', alpha=0.8)
	plt.bar(index + 3 * bar_width, fourth_thirty, bar_width, color='y', label='90-120s', alpha=0.8)
	plt.xlabel('Time (s)', fontsize='x-large')
	plt.xlim(0, 120)
	plt.xticks(np.linspace(0, 120, 5))
	plt.ylabel('Packet Loss Rate of Ping Traffic\n', fontsize='x-large')
	plt.ylim(0, 1)
	plt.yticks(np.linspace(0, 1, 11))
	plt.legend(loc='upper right', fontsize='medium')
	plt.grid(axis='y')
	plt.savefig('./results/differentpath/packetloss.png')

def plot_flow_speed():
	"""
		Plot flow speed
	"""
	bandwidth = 10.0  # (unit: Mbit/s)

	fig = plt.figure()
	fig.set_size_inches(12, 6)
	x = np.arange(0, 121)
	realtime_speed1 = get_realtime_speed('s2-eth1')
	y1 = get_value_list_throughout(realtime_speed1)
	realtime_speed2 = get_realtime_speed('s2-eth2')
	y2 = get_value_list_throughout(realtime_speed2)
	realtime_speed3 = get_realtime_speed('s2-eth3')
	y3 = get_value_list_throughout(realtime_speed3)
	plt.plot(x, y1, 'b-', linewidth=2, label="Ping")
	plt.plot(x, y2, 'r-', linewidth=2, label="Iperf1")
	plt.plot(x, y3, 'g-', linewidth=2, label="Iperf2")
	plt.xlabel('Time (s)', fontsize='x-large')
	plt.xlim(0, 120)
	plt.xticks(np.arange(0, 121, 30))
	plt.ylabel('Realtime Speed of Individual Flow\n(Mbit/s)', fontsize='x-large')
	plt.ylim(0, bandwidth)
	plt.yticks(np.linspace(0, bandwidth, 11))
	# plt.legend(loc='upper right', ncol=3, fontsize='small')
	plt.legend(loc='lower right', ncol=3, fontsize='small')
	plt.grid(True)
	plt.savefig('./results/differentpath/flowspeed.png')

def plot_throughout():
	"""
		Plot realtime throughout
	"""
	# bandwidth = 10.0  # (unit: Mbit/s)
	bandwidth = 20.0  # (unit: Mbit/s)

	fig = plt.figure()
	fig.set_size_inches(12, 6)
	x = np.arange(0, 121)
	realtime_speed = get_realtime_speed('s2-eth[1-3]')
	y = get_value_list_throughout(realtime_speed)
	plt.plot(x, y, 'r-', linewidth=2)
	plt.xlabel('Time (s)', fontsize='x-large')
	plt.xlim(0, 120)
	plt.xticks(np.arange(0, 121, 30))
	plt.ylabel('Network Unit Time Throughout\n(Mbit/s)', fontsize='x-large')
	plt.ylim(0, bandwidth)
	plt.yticks(np.linspace(0, bandwidth, 11))
	plt.grid(True)
	plt.savefig('./results/differentpath/throughout.png')

def plot_results():
	"""
		Plot the results
	"""
	# Get delay data
	roundtrip_delay = {}
	roundtrip_delay = get_delay_values(roundtrip_delay)

	# Plot delay of ping traffic
	plot_delay(roundtrip_delay)

	# Plot packet loss of ping traffic
	plot_packet_loss(roundtrip_delay)

	# Plot flow speed
	plot_flow_speed()

	# Plot realtime total throughout
	plot_throughout()

	# bandwidth = 10.0   # (unit: Mbit/s)
	# utmost_throughout = bandwidth * 120
	# total_throughout = {}
	# total_throughput = get_total_throughout(total_throughout)


if __name__ == '__main__':
	plot_results()