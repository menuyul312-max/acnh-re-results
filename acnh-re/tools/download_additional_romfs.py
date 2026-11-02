"""Download the three user-provided public Drive inputs, without modifying old inputs."""
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
import hashlib
import json
import time
import urllib.parse
import urllib.request

ROOT = Path('/workspace/downloads/acnh_additional_romfs_2026-11-02')
SOURCES = [
    ('1CSfwMVM4Aaf1-I9Kzr8blyzvr-2Zqx85', 'extracted_romfs.tar.gz'),
    ('1FBwx0gztENreNfHt2ZvvfR5IsrPZV0B9', 'KATALOG_MODEL_ACNH.csv'),
    ('1dRu6FaJ_cWN8WhKGzjZFGJzuhFzI7uvo', 'KATALOG_AUDIO_ACNH.csv'),
]


class DownloadForm(HTMLParser):
    def __init__(self):
        super().__init__()
        self.action = None
        self.fields = {}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form' and a.get('id') == 'download-form':
            self.action = a.get('action')
        if tag == 'input' and a.get('type') == 'hidden' and 'name' in a:
            self.fields[a['name']] = a.get('value', '')


def download(source):
    file_id, name = source
    target = ROOT / name
    url = 'https://drive.usercontent.google.com/download?' + urllib.parse.urlencode(
        {'id': file_id, 'export': 'download', 'confirm': 't'})
    if not target.exists():
        for attempt in range(3):
            response = urllib.request.urlopen(url, timeout=60)
            if 'text/html' not in response.headers.get('Content-Type', ''):
                break
            page = response.read(1024 * 1024).decode('utf-8', 'replace')
            response.close()
            form = DownloadForm()
            form.feed(page)
            if form.action != 'https://drive.usercontent.google.com/download':
                raise RuntimeError(f'{name}: download confirmation form unavailable')
            url = form.action + '?' + urllib.parse.urlencode(form.fields)
        else:
            raise RuntimeError(f'{name}: confirmation did not produce a file')
        with response:
            if response.status != 200 or response.headers.get('Content-Range'):
                raise RuntimeError(f'{name}: refusing partial response')
            total = response.headers.get('Content-Length')
            count = 0
            last = time.monotonic()
            partial = target.with_suffix(target.suffix + '.partial')
            with partial.open('wb') as out:
                while chunk := response.read(1024 * 1024):
                    count += len(chunk)
                    if count > 700 * 1024 * 1024:
                        raise RuntimeError(f'{name}: size exceeds download budget')
                    out.write(chunk)
                    if time.monotonic() - last > 10:
                        print(json.dumps({'downloading': name, 'bytes': count}), flush=True)
                        last = time.monotonic()
            if total and count != int(total):
                raise RuntimeError(f'{name}: response length mismatch')
            partial.rename(target)
    sha = hashlib.sha256()
    with target.open('rb') as inp:
        while chunk := inp.read(1024 * 1024):
            sha.update(chunk)
    result = {'file_id': file_id, 'source_url': f'https://drive.google.com/file/d/{file_id}/view',
              'name': name, 'path': str(target), 'bytes': target.stat().st_size,
              'sha256': sha.hexdigest()}
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(download, SOURCES))
    report = Path('/workspace/acnh-re/research/additional_romfs_downloads.json')
    report.write_text(json.dumps({'files': results}, indent=2) + '\n')
