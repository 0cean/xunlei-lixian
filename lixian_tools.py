
import lixian
import subprocess
import sys

def wget_download(url):
	client = lixian.XunleiClient(cookie_path='xunlei.cookies')
	tasks = [x for x in client.read_completed() if x['original_url'] == url]
	task = tasks[0]

	download_url = str(task['xunlei_url'])
	filename = task['name'].encode(sys.getfilesystemencoding())
	referer = str(client.get_referer())
	gdriveid = str(client.get_gdriveid())

	subprocess.call(['wget', '--header=Cookie: gdriveid='+gdriveid, download_url, '-O', filename])


