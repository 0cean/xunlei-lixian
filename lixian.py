
__all__ = ['XunleiClient']

import urllib
import urllib2
import cookielib
import re
import time
import os.path
import json
from ast import literal_eval


class XunleiClient:
	def __init__(self, username=None, password=None, cookie_path=None, login=True):
		self.cookie_path = cookie_path
		if cookie_path:
			self.cookiejar = cookielib.LWPCookieJar()
			if os.path.exists(cookie_path):
				self.load_cookies()
		else:
			self.cookiejar = cookielib.CookieJar()
		self.opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(self.cookiejar))
		if login:
			if not self.has_logged_in():
				if not username:
					if self.has_cookie('.xunlei.com', 'usernewno'):
						username = self.get_username()
					else:
						raise NotImplementedError('user is not logged in')
				if not password:
					raise NotImplementedError('user is not logged in')
				self.login(username, password)
			else:
				self.id = self.get_userid()

	def urlopen(self, url, **args):
		#print url
		if 'data' in args and type(args['data']) == dict:
			args['data'] = urllib.urlencode(args['data'])
		return self.opener.open(urllib2.Request(url, **args))

	def load_cookies(self):
		self.cookiejar.load(self.cookie_path, ignore_discard=True, ignore_expires=True)

	def save_cookies(self):
		if self.cookie_path:
			self.cookiejar.save(self.cookie_path, ignore_discard=True)

	def get_cookie(self, domain, k):
		return self.cookiejar._cookies[domain]['/'][k].value

	def has_cookie(self, domain, k):
		return domain in self.cookiejar._cookies and k in self.cookiejar._cookies[domain]['/']

	def get_userid(self):
		if self.has_cookie('.xunlei.com', 'userid'):
			return self.get_cookie('.xunlei.com', 'userid')
		else:
			raise Exception('Probably login failed')

	def get_username(self):
		return self.get_cookie('.xunlei.com', 'usernewno')

	def get_gdriveid(self):
		return self.get_cookie('.vip.xunlei.com', 'gdriveid')

	def has_gdriveid(self):
		return self.has_cookie('.vip.xunlei.com', 'gdriveid')

	def get_referer(self):
		return 'http://dynamic.cloud.vip.xunlei.com/user_task?userid=%s' % self.id

	def set_cookie(self, domain, k, v):
		c = cookielib.Cookie(version=0, name=k, value=v, port=None, port_specified=False, domain=domain, domain_specified=True, domain_initial_dot=False, path='/', path_specified=True, secure=False, expires=None, discard=True, comment=None, comment_url=None, rest={}, rfc2109=False)
		self.cookiejar.set_cookie(c)

	def set_gdriveid(self, id):
		self.set_cookie('.vip.xunlei.com', 'gdriveid', id)

	def set_page_size(self, n):
		self.set_cookie('.vip.xunlei.com', 'pagenum', str(n))

	def get_cookie_header(self):
		def domain_header(domain):
			root = self.cookiejar._cookies[domain]['/']
			return '; '.join(k+'='+root[k].value for k in root)
		return  domain_header('.xunlei.com') + '; ' + domain_header('.vip.xunlei.com')

	def has_logged_in(self):
		return len(self.urlopen('http://dynamic.lixian.vip.xunlei.com/login?cachetime=%d'%current_timestamp()).read()) > 512

	def login(self, username, password):
		cachetime = current_timestamp()
		check_url = 'http://login.xunlei.com/check?u=%s&cachetime=%d' % (username, cachetime)
		login_page = self.urlopen(check_url).read()
		verifycode = self.get_cookie('.xunlei.com', 'check_result')[2:].upper()
		def md5(s):
			import hashlib
			return hashlib.md5(s).hexdigest().lower()
		if not re.match(r'^[0-9a-f]{32}$', username):
			password = md5(md5(password))
		password = md5(password+verifycode)
		login_page = self.urlopen('http://login.xunlei.com/sec2login/', data={'u': username, 'p': password, 'verifycode': verifycode})
		self.id = self.get_userid()
		login_page = self.urlopen('http://dynamic.lixian.vip.xunlei.com/login?cachetime=%d&from=0'%current_timestamp())
		self.save_cookies()

	def logout(self):
		#session_id = self.get_cookie('.xunlei.com', 'sessionid')
		#timestamp = current_timestamp()
		#url = 'http://login.xunlei.com/unregister?sessionid=%s&cachetime=%s&noCacheIE=%s' % (session_id, timestamp, timestamp)
		#self.urlopen(url).read()
		#self.urlopen('http://dynamic.vip.xunlei.com/login/indexlogin_contr/logout/').read()
		ckeys = ["vip_isvip","lx_sessionid","vip_level","lx_login","dl_enable","in_xl","ucid","lixian_section"];
		ckeys1 = ["sessionid","usrname","nickname","usernewno","userid"];
		for k in ckeys:
			self.set_cookie('.vip.xunlei.com', k, '')
		for k in ckeys1:
			self.set_cookie('.xunlei.com', k, '')
		self.save_cookies()

	def list_bt(self, task):
		url = 'http://dynamic.cloud.vip.xunlei.com/interface/fill_bt_list?callback=fill_bt_list&tid=%s&infoid=%s&g_net=1&p=1&uid=%s&noCacheIE=%s' % (task['id'], task['bt_hash'], self.id, current_timestamp())
		html = self.urlopen(url).read().decode('utf-8')
		return parse_bt_list(html)

	def read_task_page_url(self, url):
		req = self.urlopen(url)
		page = req.read().decode('utf-8')
		if not self.has_gdriveid():
			gdriveid = re.search(r'id="cok" value="([^"]+)"', page).group(1)
			self.set_gdriveid(gdriveid)
			self.save_cookies()
		links = parse_links(page)
		pginfo = re.search(r'<div class="pginfo">.*?</div>', page)
		match_next_page = re.search(r'<li class="next"><a href="([^"]+)">[^<>]*</a></li>', page)
		return links, match_next_page and 'http://dynamic.cloud.vip.xunlei.com'+match_next_page.group(1)

	def read_task_page(self, st, pg=None):
		if pg is None:
			url = 'http://dynamic.cloud.vip.xunlei.com/user_task?userid=%s&st=%d' % (self.id, st)
		else:
			url = 'http://dynamic.cloud.vip.xunlei.com/user_task?userid=%s&st=%d&p=%d' % (self.id, st, pg)
		return self.read_task_page_url(url)

	def read_tasks(self, st=0):
		return self.read_task_page(st)[0]

	def read_all_tasks(self, st=0):
		all_links = []
		links, next_link = self.read_task_page(st)
		all_links.extend(links)
		while next_link:
			links, next_link = self.read_task_page_url(next_link)
			all_links.extend(links)
		return all_links

	def read_completed(self):
		return self.read_tasks(2)

	def read_all_completed(self):
		return self.read_all_tasks(2)

	def add_task(self, url):
		assert url.startswith('ed2k://'), 'task "%s" is not suppoted (only ed2k is tested, will support others later)' % url

		from random import randint
		random = '%s%06d.%s' % (current_timestamp(), randint(0, 999999), randint(100000000, 9999999999))
		check_url = 'http://dynamic.cloud.vip.xunlei.com/interface/task_check?callback=queryCid&url=%s&random=%s&tcache=%s' % (urllib.quote(url), random, current_timestamp())
		js = self.urlopen(check_url).read().decode('utf-8')
		qcid = re.match(r'^queryCid(\(.+\))\s*$', js).group(1)
		cid, gcid, size_required, filename, goldbean_need, silverbean_need, is_full, random = literal_eval(qcid)
		assert goldbean_need == 0
		assert silverbean_need == 0


		if url.startswith('htt:'):
			task_type = 0
		elif url.startswith('ed2k://'):
			task_type = 2
		else:
			raise NotImplementedError()
		task_url = 'http://dynamic.cloud.vip.xunlei.com/interface/task_commit?'+urllib.urlencode(
		   {'callback': 'ret_task',
		    'uid': self.id,
		    'cid': cid,
		    'gcid': gcid,
		    'size': size_required,
		    'goldbean': goldbean_need,
		    'silverbean': silverbean_need,
		    't': filename,
		    'url': url,
			'type': task_type,
		    'o_page': 'task',
		    'o_taskid': '0',
		    })

		response = self.urlopen(task_url).read()
		assert response == "<script>top.location='http://dynamic.cloud.vip.xunlei.com/user_task?userid="+self.id+"&st=0'</script>"

	def add_batch_tasks(self, urls):
		assert urls
		urls = list(urls)
		#self.urlopen('http://dynamic.cloud.vip.xunlei.com/interface/batch_task_check', data={'url':'\r\n'.join(urls), 'random':current_random()})
		url = 'http://dynamic.cloud.vip.xunlei.com/interface/batch_task_commit'
		batch_old_taskid = '0' + ',' * (len(urls) - 1) # XXX: what is it?
		data = {}
		for i in range(len(urls)):
			data['cid[%d]' % i] = ''
			data['url[%d]' % i] = urls[i]
		data['batch_old_taskid' ] = batch_old_taskid
		response = self.urlopen(url, data=data).read()
		assert response == "<script>top.location='http://dynamic.cloud.vip.xunlei.com/user_task?userid=%s&st=0'</script>" % self.id

	def add_torrent_task(self, path):
		upload_url = 'http://dynamic.cloud.vip.xunlei.com/interface/torrent_upload'
		commit_url = 'http://dynamic.cloud.vip.xunlei.com/interface/bt_task_commit'

		with open(path, 'rb') as x:
			content_type, body = encode_multipart_formdata([], [('filepath', path, x.read())])
			response = self.urlopen(upload_url, data=body, headers={'Content-Type': content_type}).read().decode('utf-8')

		upload_success = re.search(r'<script>document\.domain="xunlei\.com";var btResult =(\{.*\});</script>', response, flags=re.S)
		if upload_success:
			bt = json.loads(upload_success.group(1))
			bt_hash = bt['infoid']
			bt_name = bt['ftitle']
			bt_size = bt['btsize']
			data = {'uid':self.id, 'btname':bt_name, 'cid':bt_hash, 'tsize':bt_size,
					'findex':''.join(f['id']+'_' for f in bt['filelist']),
					'size':''.join(f['subsize']+'_' for f in bt['filelist']),
					'from':'0'}
			response = self.urlopen(commit_url, data=data).read()
			assert response == "<script>top.location='http://dynamic.cloud.vip.xunlei.com/user_task?userid=%s&st=0'</script>" % self.id
			return
		already_exists = re.search(r"parent\.edit_bt_list\((\{.*\}),''\)", response, flags=re.S)
		if already_exists:
			raise NotImplementedError()
			print json.loads(already_exists.group(1))
			return
		raise NotImplementedError()

	def delete_tasks_by_id(self, ids):
		url = 'http://dynamic.cloud.vip.xunlei.com/interface/task_delete?type=%s&taskids=%s&noCacheIE=%s' % (2, ','.join(ids)+',', current_timestamp()) # XXX: what is 'type'?
		response = json.loads(re.match(r'^delete_task_resp\((.+)\)$', self.urlopen(url).read()).group(1))
		assert response['result'] == 1
		assert response['type'] == 2

	def delete_task_by_id(self, id):
		self.delete_tasks_by_id([id])

	def delete_task(self, task):
		self.delete_task_by_id(task['id'])

	def delete_tasks(self, tasks):
		self.delete_tasks_by_id(t['id'] for t in tasks)

	def pause_tasks_by_id(self, ids):
		url = 'http://dynamic.cloud.vip.xunlei.com/interface/task_pause?tid=%s&uid=%s&noCacheIE=%s' % (','.join(ids)+',', self.id, current_timestamp())
		assert self.urlopen(url).read() == 'pause_task_resp()'

	def pause_task_by_id(self, id):
		self.pause_tasks_by_id([id])

	def pause_task(self, task):
		self.pause_task_by_id(task['id'])

	def pause_tasks(self, tasks):
		self.pause_tasks_by_id(t['id'] for t in tasks)

	def restart_tasks(self, tasks):
		url = 'http://dynamic.cloud.vip.xunlei.com/interface/redownload'
		form = []
		for task in tasks:
			assert task['type'] in ('ed2k', 'http', 'https'), "'%s' is not tested" % task['type']
			data = {'id[]': task['id'],
					'cid[]': '',
					'url[]': task['original_url'],
					'download_status[]': task['status']}
			if task['type'] == 'ed2k':
				data['taskname[]'] = task['name'].encode('utf-8')
			form.append(urllib.urlencode(data))
		form.append(urllib.urlencode({'type':1}))
		data = '&'.join(form)
		response = self.urlopen(url, data=data).read()
		assert response == "<script>document.domain='xunlei.com';window.parent.redownload_resp(1)</script>"

	def restart_task(self, task):
		self.restart_tasks([task])

	def get_task_by_id(self, id):
		tasks = self.read_all_tasks(0)
		for x in tasks:
			if x['id'] == id:
				return x
		raise Exception, 'Not task found for id '+id

def current_timestamp():
	return int(time.time()*1000)

def current_random():
	from random import randint
	return '%s%06d.%s' % (current_timestamp(), randint(0, 999999), randint(100000000, 9999999999))

def parse_link(html):
	inputs = re.findall(r'<input[^<>]+/>', html)
	def parse_attrs(html):
		return dict((k, v1 or v2) for k, v1, v2 in re.findall(r'''\b(\w+)=(?:'([^']*)'|"([^"]*)")''', html))
	info = dict((x['id'], x['value']) for x in map(parse_attrs, inputs))
	mini_info = {}
	mini_map = {}
	#mini_info = dict((re.sub(r'\d+$', '', k), info[k]) for k in info)
	for k in info:
		mini_key = re.sub(r'\d+$', '', k)
		mini_info[mini_key] = info[k]
		mini_map[mini_key] = k
	taskid = mini_map['durl'][4:]
	url = mini_info['f_url']
	task_type = re.match(r'[^:]+', url).group()
	task = {'id': taskid,
			'type': task_type,
			'name': mini_info['durl'],
			'status': int(mini_info['d_status']),
			'status_text': {'0':'waiting', '1':'downloading', '2':'completed', '3':'failed', '5':'pending'}[mini_info['d_status']],
			'size': int(mini_info['ysfilesize']),
			'original_url': mini_info['f_url'],
			'xunlei_url': mini_info['dl_url'],
			'bt_hash': mini_info['dcid'],
			'dcid': mini_info['dcid'],
			}
	# XXX: should I return bt files?
	return task

def parse_links(html):
	rwbox = re.search(r'<div class="rwbox".*<!--rwbox-->', html, re.S).group()
	rw_lists = re.findall(r'<div class="rw_list".*?<!-- rw_list -->', rwbox, re.S)
	return map(parse_link, rw_lists)

def parse_bt_list(js):
	result = json.loads(re.match(r'^fill_bt_list\((.+)\)\s*$', js).group(1))['Result']
	files = []
	for record in result['Record']:
		files.append({
			'id': record['taskid'],
			'type': 'bt',
			'name': record['title'], # TODO: support folder
			'status': int(record['download_status']),
			'status_text': {'0':'waiting', '1':'downloading', '2':'completed', '3':'failed'}[record['download_status']],
			'size': record['filesize'],
			'original_url': record['url'],
			'xunlei_url': record['downurl'],
			'dcid': record['cid'],
			})
	return files

def encode_multipart_formdata(fields, files):
	#http://code.activestate.com/recipes/146306/
	"""
	fields is a sequence of (name, value) elements for regular form fields.
	files is a sequence of (name, filename, value) elements for data to be uploaded as files
	Return (content_type, body) ready for httplib.HTTP instance
	"""
	BOUNDARY = '----------ThIs_Is_tHe_bouNdaRY_$'
	CRLF = '\r\n'
	L = []
	for (key, value) in fields:
		L.append('--' + BOUNDARY)
		L.append('Content-Disposition: form-data; name="%s"' % key)
		L.append('')
		L.append(value)
	for (key, filename, value) in files:
		L.append('--' + BOUNDARY)
		L.append('Content-Disposition: form-data; name="%s"; filename="%s"' % (key, filename))
		L.append('Content-Type: %s' % get_content_type(filename))
		L.append('')
		L.append(value)
	L.append('--' + BOUNDARY + '--')
	L.append('')
	body = CRLF.join(L)
	content_type = 'multipart/form-data; boundary=%s' % BOUNDARY
	return content_type, body

def get_content_type(filename):
	import mimetypes
	return mimetypes.guess_type(filename)[0] or 'application/octet-stream'


