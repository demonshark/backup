#!/usr/bin/python

# --------------------------------------------------------------------------
# "THE BEER-WARE LICENSE" (Revision 42):
# <ricardo.serro@gmail.com> wrote this file. As long as you retain this 
# notice you can do whatever you want with this stuff. If we meet some day, 
# and you think this stuff is worth it, you can buy me a beer in return 
# Ricardo Serro
# --------------------------------------------------------------------------
#
# Script to backup files and/or mysql databases from some of my sites.
# Uses ssh, scp, tar, mysqldump and mail.

import sys
import time
from subprocess import call
import pexpect
import pxssh

bkp = {
	# Local dir to store backups
	'loc_dir' : '/Users/ricardoserro/Temp',
	# Backup naming
	'name' : time.strftime('%Y-%m-%d-%H-%M-%S'),
	# Timeout in seconds
	'timeout' : 3600,
	# Shoud backup dirs?
	'dirs' : True,
	# Shoud backup database?
	'db' : True,
}

mail = {
	'to' : 'ricardo.serro@gmail.com',
	# Success subject. Leave blank to not recieve.
	'success' : 'Backup OK Site X',
	# Failure subject. Leave blank to not recieve.
	'failure' : 'Backup Error Site X'
}

ssh = {
	'host' : 'host.com.br',
	'user' : 'ricardo',
	'pass' : 'serro',
	# Temporary dir to build the backup archives. Must already exist.
	'temp' : '/home/sitex/bkp_tmp',
	# Dirs to be archived written as tuples (archive_name, dir_path).
	'dirs' : [
		('public_html' , '/home/sitex/public_html')
	]
}

mysql = {
	'host' : 'host.com.br',
	'user' : 'ricardo',
	'pass' : 'serro',
	'db' : 'dummy'
}

def check_exit_code(s):
	exit_code = s.before.split('\n')[-2].strip()
	if exit_code != '0':
		raise Exception('Last command exit code: ' + str(exit_code))

def dirs(s):
	global ssh
	# tar cvzf dirs
	for (name, path) in ssh['dirs']:
		sc = path.count('/') - 1
		s.sendline('tar cvzf ' + name + '.tar.gz --strip-components=' 
			+ str(sc) + ' ' + path + ' && echo $?')
		s.prompt()
		check_exit_code(s)

def db(s, log):
	global mysql
	# mysql dump
	log.write("\n" + '# MySQL: dumping from ' + mysql['host'] + "\n")
	s.logfile = None
	s.sendline('mysqldump -h ' + mysql['host'] + ' -u ' + mysql['user'] 
		+ ' -p\'' + mysql['pass'] + '\' ' + mysql['db'] + ' > ' 
		+ mysql['db'] + '.sql && echo $?')
	s.prompt()
	check_exit_code(s)
	s.logfile = log
	# tar cvzf mysql
	s.sendline('tar cvzf ' + mysql['db'] + '.tar.gz ' + mysql['db'] + '.sql' 
		+ ' && echo $?')
	s.prompt()
	check_exit_code(s)

def ssh_login(log):
	global ssh
	log.write("\n" + '# SSH: connecting to ' + ssh['host'] + "\n")
	s = pxssh.pxssh(timeout=bkp['timeout'], logfile=None)
	s.login(ssh['host'], ssh['user'], ssh['pass'])
	s.logfile = log
	s.sendline('cd ' + ssh['temp'])
	s.prompt()
	s.sendline('pwd')
	s.prompt()
	pwd = s.before.split('\n')[1].strip()
	if pwd != ssh['temp']:
		raise Exception('Unable to reach ' + ssh['temp'])
	return s

def ssh_logout(s):
	s.sendline('history -c')
	s.prompt()
	s.logout()

def archive(log):
	global bkp, ssh, mysql
	if not bkp['dirs'] and not bkp['db']:
		raise Exception('Nothing to backup.')
	
	# Login & Archive
	s = ssh_login(log)
	if bkp['dirs']:
		dirs(s)
	if bkp['db']:
		db(s, log)

	# 1 Tar
	tar = 'tar cvf ' + bkp['name'] + '.tar'
	if bkp['dirs']:
		for (name, path) in ssh['dirs']:
			tar = tar + ' ' + name + '.tar.gz'
	if bkp['db']:
		tar = tar + ' ' + mysql['db'] + '.tar.gz'
	s.sendline(tar + ' && echo $?')
	s.prompt()
	check_exit_code(s)

	# Logout
	ssh_logout(s)

def copy(log):
	global bkp, ssh
	log.write("\n" + '# SCP: copying from ' + ssh['host'] + "\n")
	p = pexpect.spawn('scp -oPubkeyAuthentication=no ' + ssh['user'] 
		+ '@' + ssh['host'] + ':' + ssh['temp'] + '/' + bkp['name'] 
		+ '.tar ' + bkp['loc_dir'], timeout=bkp['timeout'], logfile=None)
	i = p.expect(['assword:', r"yes/no"])
	if i == 1:
		p.sendline('yes')
	p.sendline(ssh['pass'])
	p.logfile = log
	p.expect(pexpect.EOF)
	p.close()
	if p.exitstatus != 0:
		raise Exception('SCP copy error. Exit code differ from zero.')

def clean(log):
	log.write("\n" + '# Cleaning...' + "\n")
	s = ssh_login(log)
	s.sendline('rm -rf * && echo $?')
	s.prompt()
	check_exit_code(s)
	ssh_logout(s)

def backup():
	global bkp, mail

	# Backup actions
	log_path = bkp['loc_dir'] + '/' + bkp['name'] + '.log'
	log = file(log_path, 'w')
	log.write("\n" + '# Start ' + time.strftime('%Y-%m-%d %H:%M:%S') + "\n")
	exc = None
	try:
		archive(log)
		copy(log)
		clean(log)
	except Exception as e:
		exc = str(e) + "\n"
		log.write(exc)
	log.write("\n" + '# End ' + time.strftime('%Y-%m-%d %H:%M:%S') + "\n")
	log.close()

	# Exit Status & Emailing Actions
	if exc:
		print 'failure'
		if mail['failure']:
			call('cat ' + log_path + ' | mail -s "' + mail['failure'] 
				+ '" "' + mail['to'] + '"', shell=True)
		return 1
	else:
		print 'success'
		if mail['success']:
			call('cat ' + log_path + ' | mail -s "' + mail['success'] 
				+ '" "' + mail['to'] + '"', shell=True)
		return 0

def main(argv):
	sys.exit(backup())

if __name__ == "__main__":
	main(sys.argv)
