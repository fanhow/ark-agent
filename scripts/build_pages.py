#!/usr/bin/env python3
"""Only an explicit public allowlist is copied. Never export private data/ or .env."""
from pathlib import Path
import argparse,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',default=str(ROOT/'site'));a=p.parse_args();out=Path(a.output).resolve()
if out==ROOT or ROOT in out.parents and out.name!='site':raise ValueError('輸出目錄須為 site 或外部暫存目錄')
out.mkdir(parents=True,exist_ok=True)
def copy_tree(source,target):
 # Generated assets need contents only; do not copy macOS file flags.
 for entry in source.rglob('*'):
  dest=target/entry.relative_to(source)
  if entry.is_dir():dest.mkdir(parents=True,exist_ok=True)
  else:dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(entry,dest)
# Remove previous published assets only; site/ is generated and git-ignored.
for old in out.iterdir():
 if old.is_dir():shutil.rmtree(old)
 else:old.unlink()
for name in ['index.html','app.js','lib.js','macro.js','fund.js','fund-model.js','fund.css','storage.js','styles.css','crew.json']:shutil.copyfile(ROOT/name,out/name)
copy_tree(ROOT/'assets',out/'assets')
(out/'data').mkdir();shutil.copyfile(ROOT/'data/portfolio.initial.json',out/'data/portfolio.initial.json')
copy_tree(ROOT/'public/briefs',out/'data/briefs')
(out/'config.json').write_text(json.dumps({'mode':'pages'},ensure_ascii=False)+'\n')
(out/'.nojekyll').touch()
print('GitHub Pages build:',out)
