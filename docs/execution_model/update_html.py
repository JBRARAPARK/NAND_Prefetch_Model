"""Refresh the standalone GUI's embedded data and parameter options."""
import html
import json
import re
from pathlib import Path
from generate_data import LOOKUPS

folder = Path(__file__).resolve().parent
path = folder / 'index.html'
data = json.loads((folder / 'data.json').read_text())
expected = {f'{s}|{m}|{o}|{l:g}' for s in ['ready', 'none', 'late', 'mixed']
            for m in ['striped', 'single'] for o in range(1, 65) for l in LOOKUPS}
assert set(data) == expected, 'Incomplete simulation grid'
source = path.read_text()
match = re.search(r'data-srcdoc="([\s\S]*?)"', source)
assert match, 'Missing standalone frame'
inner = html.unescape(match.group(1))
options = ''.join(f'<option value="{v:g}"'+(' selected' if v == .768 else '')+
                  f'>{v:g}µs'+(' (경계값)' if v == .768 else '')+'</option>' for v in LOOKUPS)
inner, count = re.subn(r'(<select[^>]*id="nm-lookup"[^>]*>).*?(</select>)',
                      lambda m: m[1]+options+m[2], inner, flags=re.S)
assert count == 1
inner, count = re.subn(r'(<script type="application/json" id="nm-data">).*?(</script>)',
                      lambda m: m[1]+json.dumps(data, separators=(',', ':'))+m[2], inner, flags=re.S)
assert count == 1
path.write_text(source[:match.start(1)]+html.escape(inner, quote=True)+source[match.end(1):])
print(f'GUI updated: {len(data)} combinations, {len(LOOKUPS)} lookup values')
