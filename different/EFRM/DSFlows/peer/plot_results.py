# coding=utf-8

import os
import xlwt

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
		if line.endswith('%)\n'):
			lines_list.append(line)
	read_file.close()
	return lines_list

def calculate_average(value_list):
	average_value = sum(map(float, value_list)) / len(value_list)
	return average_value

def get_bandwidth(throughout_path, number):
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
							# throughout = line[20: 26].strip()
							bandwidth = float(line[34: 39].strip()) / number
							# throughout_number = throughout_number + float(throughout)
							if float(bandwidth) > 0 and float(bandwidth) <= 1:
								bandwidth_number_all = bandwidth_number_all + 1
								bandwidth_number = bandwidth_number + float(bandwidth)
							
		bandwidth = float(bandwidth_number / bandwidth_number_all)

	return bandwidth

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
							times = str(line[6: 10].strip())
							timestop = str(line[11: 16].strip())
							timeall = float(timestop) - float(times)
							throughout = str(line[20: 26].strip())
							bandwidth = line[34: 38].strip()
							throughout_number = throughout_number + float((float(throughout) * 8) / timeall) * 10
							if float(bandwidth) > 0:
								bandwidth_number_all = bandwidth_number_all + 1
								bandwidth_number = bandwidth_number + float(bandwidth)

		bandwidth = round(bandwidth_number / bandwidth_number_all, 2)
		# print(bandwidth)

	return throughout_number

def get_packet(throughout_path):
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
							# print(line)
							# times = str(line[6: 10].strip())
							# timestop = str(line[11: 16].strip())
							# timeall = float(timestop) - float(times)
							# throughout = str(line[20: 26].strip())
							begin = line.find('(') + 1
							end = line.find(")") - 1
							bandwidth = line[begin: end].strip()
							# throughout_number = throughout_number + float((float(throughout) * 8) / timeall) * 10
							# if float(bandwidth) > 0:
							bandwidth_number_all = bandwidth_number_all + 1
							bandwidth_number = bandwidth_number + float(bandwidth)
							# print(bandwidth)

		bandwidth = round(bandwidth_number / bandwidth_number_all, 2)
		# print(bandwidth)

	return bandwidth

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
	workbook = xlwt.Workbook(encoding = 'utf-8')
	worksheet = workbook.add_sheet('test')
	methods = 0
	for i in xrange(5):
		worksheet.write(1, methods, label="ecmp")
		worksheet.write(1, methods + 1, label="hedera")
		worksheet.write(1, methods + 2, label="dsfm")
		worksheet.write(1, methods + 3, label="adaptive")
		worksheet.write(1, methods + 4, label="fixed")
		methods = methods + 6
	# workbook.save('1.xls')
	# for i in xrange(6):
		# file_bandwidth = '../result/ecmp/stride4/' + str(i + 1) + '/'
		# file_bandwidth = file_bandwidth
		# delay_packet_file = file_bandwidth + '/successive_packets.txt'
		# delay_packet = {}
		# delay_packet = get_delay_packet(delay_packet, delay_packet_file)
		# throughout = get_throughout(file_bandwidth)

		# print('ecmp average_delay:' + str(delay_packet['average_delay']))
		# print('mean_delay:' + str(delay_packet['mean_delay']))
		# print('ecmp packet_loss:' + str(delay_packet['packet_loss']))
		# print('ecmp throught:' + str(throughout))

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
	r = 2
	l = 0
	b = 2
	for i in xrange(9):
		for j in xrange(5):
			# file_ecmp = '../data/ecmp/' + str(i + 1) + '/'
			# file_ecmp = file_ecmp + str(j + 1)
			# delay_packet_file_ecmp = file_ecmp + '/successive_packets.txt'
			# delay_packet_ecmp = {}
			# delay_packet_ecmp = get_delay_packet(delay_packet_ecmp, delay_packet_file_ecmp)
			# bandwidth_ecmp = str(get_bandwidth(file_ecmp, b))
			# throughout_ecmp = str(get_throughout(file_ecmp))
			# delay_ecmp = str(delay_packet_ecmp['average_delay'])
			# packet_ecmp = str(delay_packet_ecmp['packet_loss'])
			# packet_ecmp_flows = get_packet(file_ecmp)
			
			# print('ecmp average_delay:' + str(delay_packet_ecmp['average_delay']))
			# print('ecmp mean_delay:' + str(delay_packet_ecmp['mean_delay']))
			# print('ecmp packet_loss:' + str(delay_packet_ecmp['packet_loss']))
			# print('ecmp bandwidth:' + str(bandwidth_ecmp))
			# print('ecmp throughout:' + str(throughout_ecmp))
			# print('ecmp packet:' + str(packet_ecmp_flows))

			# file_hedera = '../data/hedera/' + str(i + 1) + '/'
			# file_hedera = file_hedera + str(j + 1)
			# delay_packet_file_hedera = file_hedera + '/successive_packets.txt'
			# delay_packet_hedera = {}
			# delay_packet_hedera = get_delay_packet(delay_packet_hedera, delay_packet_file_hedera)
			# bandwidth_hedera = get_bandwidth(file_hedera, b)
			# throughout_hedera = str(get_throughout(file_hedera))
			# delay_hedera = str(delay_packet_hedera['average_delay'])
			# packet_hedera = str(delay_packet_hedera['packet_loss'])
			# packet_hedera_flows = get_packet(file_hedera)
			
			# print('hedera average_delay:' + str(delay_packet_hedera['average_delay']))
			# print('hedera mean_delay:' + str(delay_packet_hedera['mean_delay']))
			# print('hedera packet_loss:' + str(delay_packet_hedera['packet_loss']))
			# print('hedera bandwidth:' + str(bandwidth_hedera))
			# print('hedera throughout:' + str(throughout_hedera))
			# print('hedera packet:' + str(packet_hedera_flows))

			# file_ashman = '../data/ASHMAN/'
			# file_ashman = file_ashman
			# delay_packet_file_ashman = file_ashman + '/successive_packets.txt'
			# delay_packet_ashman = {}
			# delay_packet_ashman = get_delay_packet(delay_packet_ashman, delay_packet_file_ashman)
			# bandwidth_ashman = get_bandwidth(file_ashman, 5)
			# throughout_ashman = get_throughout(file_ashman)
			# delay_ashman = str(delay_packet_ashman['average_delay'])
			# packet_ashman = str(delay_packet_ashman['mean_delay'])
			
			# print('ashman average_delay:' + str(delay_packet_ashman['average_delay']))
			# print('ashman mean_delay:' + str(delay_packet_ashman['mean_delay']))
			# print('ashman packet_loss:' + str(delay_packet_ashman['packet_loss']))
			# print('ashman bandwidth:' + str(throughout_ashman))

			# file_dsflows = '../data/DSFlows/'
			# file_dsflows = file_dsflows
			# delay_packet_file_dsflows = file_dsflows + '/successive_packets.txt'
			# delay_packet_dsflows = {}
			# delay_packet_dsflows = get_delay_packet(delay_packet_dsflows, delay_packet_file_dsflows)
			# bandwidth_dsflows = get_bandwidth(file_dsflows, 5)
			# throughout_dsflows = get_throughout(file_dsflows)
			# delay_dsflows = str(delay_packet_dsflows['average_delay'])
			# packet_dsflows = str(delay_packet_dsflows['packet_loss'])
			
			# print('dsflows average_delay:' + str(delay_packet_dsflows['average_delay']))
			# print('dsflows mean_delay:' + str(delay_packet_dsflows['mean_delay']))
			# print('dsflows packet_loss:' + str(delay_packet_dsflows['packet_loss']))
			# print('dsflows bandwidth:' + str(bandwidth_dsflows))
			# print('dsflows throughout:' + str(throughout_dsflows))
			# print('\n')

			# file_dsfm = '../data/dsfm/' + str(i + 1) + '/'
			# file_dsfm = file_dsfm + str(j + 1)
			# delay_packet_file_dsfm = file_dsfm + '/successive_packets.txt'
			# delay_packet_dsfm = {}
			# delay_packet_dsfm = get_delay_packet(delay_packet_dsfm, delay_packet_file_dsfm)
			# bandwidth_dsfm = get_bandwidth(file_dsfm, b)
			# throughout_dsfm = get_throughout(file_dsfm)
			# delay_dsfm = str(delay_packet_dsfm['average_delay'])
			# packet_dsfm = str(delay_packet_dsfm['packet_loss'])
			# packet_dsfm_flows = get_packet(file_dsfm)
			
			# print('DSFM average_delay:' + str(delay_packet_dsfm['average_delay']))
			# print('DSFM mean_delay:' + str(delay_packet_dsfm['mean_delay']))
			# print('DSFM packet_loss:' + str(delay_packet_dsfm['packet_loss']))
			# print('DSFM bandwidth:' + str(bandwidth_dsfm))
			# print('DSFM throughout:' + str(throughout_dsfm))
			# print('DSFM packet:' + str(packet_dsfm_flows))
			# print('\n')

			# file_adaptive = '../data/adaptive/' + str(i + 1) +'/'
			# file_adaptive = file_adaptive + str(j + 1)
			# delay_packet_file_adaptive = file_adaptive + '/successive_packets.txt'
			# delay_packet_adaptive = {}
			# delay_packet_adaptive = get_delay_packet(delay_packet_adaptive, delay_packet_file_adaptive)
			# bandwidth_adaptive = get_bandwidth(file_adaptive, b)
			# throughout_adaptive = get_throughout(file_adaptive)
			# delay_adaptive = str(delay_packet_adaptive['average_delay'])
			# packet_adaptive = str(delay_packet_adaptive['packet_loss'])
			# packet_adaptive_flows = get_packet(file_adaptive)
			
			# print('adaptive average_delay:' + str(delay_packet_adaptive['average_delay']))
			# print('adaptive mean_delay:' + str(delay_packet_adaptive['mean_delay']))
			# print('adaptive packet_loss:' + str(delay_packet_adaptive['packet_loss']))
			# print('adaptive bandwidth:' + str(bandwidth_adaptive))
			# print('adaptive throughout:' + str(throughout_adaptive))
			# print('adaptive packet:' + str(packet_adaptive_flows))
			# print('\n')

			file_ashman = '../data/ashman/' + str(i + 1) +'/'
			file_ashman = file_ashman + str(j + 1)
			delay_packet_file_ashman = file_ashman + '/successive_packets.txt'
			delay_packet_ashman = {}
			delay_packet_ashman = get_delay_packet(delay_packet_ashman, delay_packet_file_ashman)
			bandwidth_ashman = get_bandwidth(file_ashman, b)
			throughout_ashman = get_throughout(file_ashman)
			delay_ashman = str(delay_packet_ashman['average_delay'])
			packet_ashman = str(delay_packet_ashman['packet_loss'])
			packet_ashman_flows = get_packet(file_ashman)

			# file_fixed = '../data/fixed/' + str(i + 1) + '/'
			# file_fixed = file_fixed + str(j + 1)
			# delay_packet_file_fixed = file_fixed + '/successive_packets.txt'
			# delay_packet_fixed = {}
			# delay_packet_fixed = get_delay_packet(delay_packet_fixed, delay_packet_file_fixed)
			# bandwidth_fixed = get_bandwidth(file_fixed, b)
			# throughout_fixed = get_throughout(file_fixed)
			# delay_fixed = str(delay_packet_fixed['average_delay'])
			# packet_fixed = str(delay_packet_fixed['packet_loss'])
			# packet_fixed_flows = get_packet(file_fixed)
			# print('fixed average_delay:' + str(delay_packet_fixed['average_delay']))
			# print('fixed mean_delay:' + str(delay_packet_fixed['mean_delay']))
			# print('fixed packet_loss:' + str(delay_packet_fixed['packet_loss']))
			# print('fixed bandwidth:' + str(bandwidth_fixed))
			# print('fixed throughout:' + str(throughout_fixed))
			# print('fixed packet:' + str(packet_fixed_flows))
			# print('\n')

			# b = b + 0.5

			# worksheet.write(r, 0, label=delay_ecmp)
			# worksheet.write(r, 1, label=delay_hedera)
			# worksheet.write(r, 2, label=delay_dsfm)
			# worksheet.write(r, 3, label=delay_adaptive)
			worksheet.write(r, 4, label=delay_ashman)

			# worksheet.write(r, 6, label=packet_ecmp)
			# worksheet.write(r, 7, label=packet_hedera)
			# worksheet.write(r, 8, label=packet_dsfm)
			# worksheet.write(r, 9, label=packet_adaptive)
			worksheet.write(r, 10, label=packet_ashman)

			# worksheet.write(r, 12, label=bandwidth_ecmp)
			# worksheet.write(r, 13, label=bandwidth_hedera)
			# worksheet.write(r, 14, label=bandwidth_dsfm)
			# worksheet.write(r, 15, label=bandwidth_adaptive)
			worksheet.write(r, 16, label=bandwidth_ashman)

			# worksheet.write(r, 18, label=throughout_ecmp)
			# worksheet.write(r, 19, label=throughout_hedera)
			# worksheet.write(r, 20, label=throughout_dsfm)
			# worksheet.write(r, 21, label=throughout_adaptive)
			worksheet.write(r, 22, label=throughout_ashman)

			# worksheet.write(r, 24, label=packet_ecmp_flows)
			# worksheet.write(r, 25, label=packet_hedera_flows)
			# worksheet.write(r, 26, label=packet_dsfm_flows)
			# worksheet.write(r, 27, label=packet_adaptive_flows)
			worksheet.write(r, 28, label=packet_ashman_flows)
			r = r + 1
		r = r + 1
		r = r + 1
		b = b + 0.5
	workbook.save('t15.xls')

if __name__ == '__main__':
	get_result()