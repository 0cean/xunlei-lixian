
from lixian_query import Query
from lixian_query import query
from lixian_query import bt_query

import lixian_hash_bt
import lixian_url

import re

##################################################
# queries
##################################################

class SingleTaskQuery(Query):
	def __init__(self, base, t):
		super(SingleTaskQuery, self).__init__(base)
		self.id = t['id']

	def get_tasks(self):
		return [self.base.get_task_by_id(self.id)]

@query(priority=1)
@bt_query(priority=1)
def single_id_processor(base, x):
	if not re.match(r'^\d+/?$', x):
		return
	n = x.rstrip('/')
	t = base.find_task_by_id(n)
	if t:
		return SingleTaskQuery(base, t)

##################################################

class MultipleTasksQuery(Query):
	def __init__(self, base, tasks):
		super(MultipleTasksQuery, self).__init__(base)
		self.tasks = tasks

	def get_tasks(self):
		return map(self.base.get_task_by_id, (t['id'] for t in self.tasks))

@query(priority=1)
@bt_query(priority=1)
def range_id_processor(base, x):
	m = re.match(r'^#?(\d+)-(\d+)$', x)
	if not m:
		return
	begin = int(m.group(1))
	end = int(m.group(2))
	tasks = base.get_tasks()
	if begin <= end:
		found = filter(lambda x: begin <= x['#'] <= end, tasks)
	else:
		found = reversed(filter(lambda x: end <= x['#'] <= begin, tasks))
	if found:
		return MultipleTasksQuery(base, found)

##################################################

class SubTaskQuery(Query):
	def __init__(self, base, t, subs):
		super(SubTaskQuery, self).__init__(base)
		self.task = t
		self.subs = subs

	def get_tasks(self):
		result = []
		task = self.base.get_task_by_id(self.task['id'])
		for i in self.subs:
			t = dict(task)
			t['index'] = i
			result.append(t)
		return result

@query(priority=1)
@bt_query(priority=1)
def sub_id_processor(base, x):
	m = re.match(r'^#?(\d+)/([-.\w\[\],\s*]+)$', x)
	if not m:
		return
	task_id, sub_id = m.groups()
	task = base.find_task_by_id(task_id)
	if not task:
		return

	import lixian_encoding
	assert task['type'] == 'bt', 'task %s is not a bt task' % lixian_encoding.to_native(task['name'])
	subs = []
	if re.match(r'\[.*\]', sub_id):
		for sub_id in re.split(r'\s*,\s*', sub_id[1:-1]):
			assert re.match(r'^\d+(-\d+)?|\.\w+$', sub_id), sub_id
			if sub_id.startswith('.'):
				subs.append(sub_id)
			elif '-' in sub_id:
				start, end = map(int, sub_id.split('-'))
				r = range(start, end+1) if start <= end else reversed(range(end, start+1))
				for i in r:
					subs.append(str(i))
			else:
				assert re.match(r'^\d+$', sub_id), sub_id
				subs.append(sub_id)
	elif re.match(r'^\.\w+$', sub_id):
		subs.append(sub_id)
	elif sub_id == '*':
		subs.append(sub_id)
	else:
		assert re.match(r'^\d+$', sub_id), sub_id
		subs.append(sub_id)
	return SubTaskQuery(base, task, subs)

##################################################

class DateQuery(Query):
	def __init__(self, base, x):
		super(DateQuery, self).__init__(base)
		self.text = x

	def get_tasks(self):
		return filter(lambda t: t['name'].lower().find(self.text.lower()) != -1, self.base.get_tasks())

@query(priority=1)
@bt_query(priority=1)
def date_processor(base, x):
	if re.match(r'^\d{4}\.\d{2}\.\d{2}$', x):
		matched = filter(lambda t: t['date'] == x, base.get_tasks())
		if matched:
			return MultipleTasksQuery(base, matched)

##################################################

class BtHashQuery(Query):
	def __init__(self, base, x):
		super(BtHashQuery, self).__init__(base)
		self.hash = re.match(r'^(?:bt://)?([0-9a-f]{40})$', x, flags=re.I).group(1).lower()
		self.task = self.base.find_task_by_hash(self.hash)

	def prepare(self):
		if not self.task:
			self.base.add_bt_task_by_hash(self.hash)

	def get_tasks(self):
		t = self.base.find_task_by_hash(self.hash)
		assert t, 'Task not found: bt://' + self.hash
		return [t]

@query(priority=1)
@bt_query(priority=1)
def bt_hash_processor(base, x):
	if re.match(r'^(bt://)?[0-9a-f]{40}$', x, flags=re.I):
		return BtHashQuery(base, x)

##################################################

class LocalBtQuery(Query):
	def __init__(self, base, x):
		super(LocalBtQuery, self).__init__(base)
		self.path = x
		self.hash = lixian_hash_bt.info_hash(self.path)
		self.task = self.base.find_task_by_hash(self.hash)
		with open(self.path, 'rb') as stream:
			self.torrent = stream.read()

	def prepare(self):
		if not self.task:
			self.base.add_bt_task_by_content(self.torrent, self.path)

	def get_tasks(self):
		t = self.base.find_task_by_hash(self.hash)
		assert t, 'Task not found: bt://' + self.hash
		return [t]

@query(priority=1)
@bt_query(priority=1)
def local_bt_processor(base, x):
	import os.path
	if x.lower().endswith('.torrent') and os.path.exists(x):
		return LocalBtQuery(base, x)

##################################################

class MagnetQuery(Query):
	def __init__(self, base, x):
		super(MagnetQuery, self).__init__(base)
		self.url = x
		self.hash = lixian_hash_bt.magnet_to_infohash(x).encode('hex').lower()
		self.task = self.base.find_task_by_hash(self.hash)

	def prepare(self):
		if not self.task:
			self.base.add_magnet_task(self.url)

	def get_tasks(self):
		t = self.base.find_task_by_hash(self.hash)
		assert t, 'Task not found: bt://' + self.hash
		return [t]

@query(priority=4)
@bt_query(priority=4)
def magnet_processor(base, url):
	if re.match(r'magnet:', url):
		return MagnetQuery(base, url)

##################################################

class BatchUrlsQuery(Query):
	def __init__(self, base, urls):
		super(BatchUrlsQuery, self).__init__(base)
		self.urls = urls

	def prepare(self):
		for url in self.urls:
			if not self.base.find_task_by_url(url):
				self.base.add_url_task(url)

	def get_tasks(self):
		return map(self.base.get_task_by_url, self.urls)

@query(priority=6)
@bt_query(priority=6)
def url_extend_processor(base, url):
	import lixian_extend_links
	extended = lixian_extend_links.try_to_extend_link(url)
	if extended:
		extended = map(lixian_extend_links.to_url, extended)
		return BatchUrlsQuery(base, extended)

##################################################

class UrlQuery(Query):
	def __init__(self, base, x):
		super(UrlQuery, self).__init__(base)
		self.url = lixian_url.url_unmask(x)
		self.task = self.base.find_task_by_url(self.url)

	def prepare(self):
		if not self.task:
			self.base.add_url_task(self.url)

	def get_tasks(self):
		t = self.base.find_task_by_url(self.url)
		assert t, 'Task not found: bt://' + self.url
		return [t]

@query(priority=7)
def url_processor(base, url):
	if re.match(r'\w+://', url):
		return UrlQuery(base, url)

##################################################

class BtUrlQuery(Query):
	def __init__(self, base, url, torrent):
		super(BtUrlQuery, self).__init__(base)
		self.url = url
		self.torrent = torrent
		self.hash = lixian_hash_bt.info_hash_from_content(self.torrent)
		self.task = self.base.find_task_by_hash(self.hash)

	def prepare(self):
		if not self.task:
			self.base.add_bt_task_by_content(self.torrent, self.url)

	def get_tasks(self):
		t = self.base.find_task_by_hash(self.hash)
		assert t, 'Task not found: bt://' + self.hash
		return [t]

@bt_query(priority=7)
def bt_url_processor(base, url):
	if not re.match(r'http://', url):
		return
	print 'Downloading torrent file from', url
	import urllib2
	torrent = urllib2.urlopen(url, timeout=60).read()
	return BtUrlQuery(base, url, torrent)

##################################################

class DefaultQuery(Query):
	def __init__(self, base, x):
		super(DefaultQuery, self).__init__(base)
		self.text = x

	def get_tasks(self):
		return filter(lambda t: t['name'].lower().find(self.text.lower()) != -1, self.base.get_tasks())

@query(priority=9)
@bt_query(priority=9)
def default_processor(base, x):
	return DefaultQuery(base, x)

