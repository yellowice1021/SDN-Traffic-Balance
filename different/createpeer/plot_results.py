# coding=utf-8

import os

def read_file_1(file_name, delim=','):
	"""
		Read the bwmng.txt file.
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

def read_file_2(file_name):
	"""
		Read the first_packets.txt and successive_packets.txt file.
	"""
	read_file = open(file_name, 'r')
	lines = read_file.xreadlines()
	lines_list = []
	for line in lines:
		if line.startswith('rtt') or line.endswith('ms\n'):
			lines_list.append(line)
	read_file.close()
	return lines_list

def read_throughout_file(file):
	"""
		read the file to get throughout
	"""
	read_file = open(file, 'r')
	lines = read_file.xreadlines()
	lines_list = []
	for line in lines:
		if line.endswith('/sec\n'):
			lines_list.append(line)
	read_file.close()
	return lines_list

def calculate_average(value_list):
	average_value = sum(map(float, value_list)) / len(value_list)
	return average_value

def get_throughout(throughout_path):
	"""
		get throughout
	"""
	throughout_number = 0
	bandwidth_number = 0
	bandwidth_number_all = 0

	for root, dir, file_list in os.walk(throughout_path):
		for file in file_list:
			if str(file).startswith('h'):
				throughout_file = throughout_path + '/' + str(file)
				lines = read_throughout_file(throughout_file)

				for line in lines:
					start_time = line[5: 10].strip()
					if start_time == '0.0':
						end_time = line[11: 16].strip()
						last_time = float(end_time) - float(start_time)
						if last_time > 10:
							throughout = line[20: 26].strip()
							bandwidth = line[34: 38].strip()
							throughout_number = throughout_number + float(throughout)
							if float(bandwidth) > 0:
								bandwidth_number_all = bandwidth_number_all + 1
								bandwidth_number = bandwidth_number + float(bandwidth)

		bandwidth = round(bandwidth_number / bandwidth_number_all, 2)
		print(bandwidth)

	return throughout_number

def get_delay_packet(delay_packet, file):
	"""
		get delay and packet_loss
	"""
	lines_list = read_file_2(file)
	average_delay = []
	mean_delay = []
	total_send = 0
	total_receive = 0

	for line in lines_list:
		if line.startswith('rtt'):
			average_delay.append(float(line.split('/')[4]))
			mean_delay.append(float((line.split('/')[6]).split(' ')[0]))
		else:
			total_send += int(line.split(' ')[0])
			total_receive += int(line.split(' ')[3])
	delay_packet['average_delay'] = calculate_average(average_delay)
	delay_packet['mean_delay'] = calculate_average(mean_delay)
	delay_packet['packet_loss'] = (total_send - total_receive) / float(total_send)
	return delay_packet

def get_result():
	"""
		get result of throughout, delay, packet_loss
	"""
	for i in xrange(6):
		file_bandwidth = '../result/ecmp/stride4/' + str(i + 1) + '/'
		file_bandwidth = file_bandwidth
		# delay_packet_file = file_bandwidth + '/successive_packets.txt'
		# delay_packet = {}
		# delay_packet = get_delay_packet(delay_packet, delay_packet_file)
		throughout = get_throughout(file_bandwidth)

		# print('ecmp average_delay:' + str(delay_packet['average_delay']))
		# print('mean_delay:' + str(delay_packet['mean_delay']))
		# print('ecmp packet_loss:' + str(delay_packet['packet_loss']))
		print('ecmp throught:' + str(throughout))

		# file_number = '../result/hedera/stride4/'
		# file_number = file_number + str(i + 1) + '/'
		# # delay_packet_file = file_number + '/successive_packets.txt'
		# # delay_packet = {}
		# # delay_packet = get_delay_packet(delay_packet, delay_packet_file)
		# throughout = get_throughout(file_number)
		#
		# # print('maxwidth average_delay:' + str(delay_packet['average_delay']))
		# # # print('mean_delay:' + str(delay_packet['mean_delay']))
		# # print('maxwidth packet_loss:' + str(delay_packet['packet_loss']))
		# print('hedera throught:' + str(throughout))
		#
		# file_differenttype = '../result/Ashman/stride4/'
		# file_differenttype = file_differenttype + str(i + 1) + '/'
		# # delay_packet_file = file_differenttype + '/successive_packets.txt'
		# # delay_packet = {}
		# # delay_packet = get_delay_packet(delay_packet, delay_packet_file)
		# throughout = get_throughout(file_differenttype)
		#
		# # print('differenttype average_delay:' + str(delay_packet['average_delay']))
		# # # print('mean_delay:' + str(delay_packet['mean_delay']))
		# # print('differenttype packet_loss:' + str(delay_packet['packet_loss']))
		# print('Ashman throught:' + str(throughout))
		#
		# file_flows = '../result/DSFlows/stride4/'
		# file_flows = file_flows + str(i + 1) + '/'
		# # delay_packet_file = file_differenttype + '/successive_packets.txt'
		# # delay_packet = {}
		# # delay_packet = get_delay_packet(delay_packet, delay_packet_file)
		# throughout = get_throughout(file_flows)
		#
		# # print('differenttype average_delay:' + str(delay_packet['average_delay']))
		# # # print('mean_delay:' + str(delay_packet['mean_delay']))
		# # print('differenttype packet_loss:' + str(delay_packet['packet_loss']))
		# print('DSFlows throught:' + str(throughout))
		# print('\n')

	# for i in xrange(1):
		# file_bandwidth = '../result/hotspot/ecmp/'
		# file_bandwidth = file_bandwidth + str(i + 1)
		# delay_packet_file = file_bandwidth + '/successive_packets.txt'
		# delay_packet = {}
		# delay_packet = get_delay_packet(delay_packet, delay_packet_file)
		# throughout = get_throughout(file_bandwidth)
		#
		# print('ecmp average_delay:' + str(delay_packet['average_delay']))
		# # print('mean_delay:' + str(delay_packet['mean_delay']))
		# print('ecmp packet_loss:' + str(delay_packet['packet_loss']))
		# print('ecmp throught:' + str(throughout))

		# file_number = '../result/times/maxwidth/8/hotspot/'
		# # file_number = file_number + str(i + 1)
		# delay_packet_file = file_number + '/successive_packets.txt'
		# delay_packet = {}
		# delay_packet = get_delay_packet(delay_packet, delay_packet_file)
		# throughout = get_throughout(file_number)
		#
		# print('maxwidth average_delay:' + str(delay_packet['average_delay']))
		# # print('mean_delay:' + str(delay_packet['mean_delay']))
		# print('maxwidth packet_loss:' + str(delay_packet['packet_loss']))
		# print('maxwidth throught:' + str(throughout))

		# file_differenttype = '../result/times/differenttype/2/hotspot/'
		# # file_differenttype = file_differenttype + str(i + 1)
		# delay_packet_file = file_differenttype + '/successive_packets.txt'
		# delay_packet = {}
		# delay_packet = get_delay_packet(delay_packet, delay_packet_file)
		# throughout = get_throughout(file_differenttype)
		#
		# print('differenttype average_delay:' + str(delay_packet['average_delay']))
		# # print('mean_delay:' + str(delay_packet['mean_delay']))
		# print('differenttype packet_loss:' + str(delay_packet['packet_loss']))
		# print('differenttype throught:' + str(throughout))
		# print('\n')

if __name__ == '__main__':
	get_result()