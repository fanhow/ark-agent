#!/usr/bin/env python3
"""Only an explicit public allowlist is copied. Never export private data/ or .env."""
from pathlib import Path
import argparse,json,shutil,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',default=str(ROOT/'site'));a=p.parse_args();out=Path(a.output).resolve()
if out==ROOT or ROOT in out.parents and out.name!='site':raise ValueError('輸出目錄須為 site 或外部暫存目錄')
out.mkdir(parents=True,exist_ok=True)
# Remove previous published assets only; site/ is generated and git-ignored.
for old in out.iterdir():
 if old.is_dir():shutil.rmtree(old)
 else:old.unlink()
for name in ['index.html','app.js','lib.js','macro.js','storage.js','styles.css','crew.json']:shutil.copy2(ROOT/name,out/name)
shutil.copytree(ROOT/'assets',out/'assets')
(out/'data').mkdir();shutil.copy2(ROOT/'data/portfolio.initial.json',out/'data/portfolio.initial.json')
shutil.copytree(ROOT/'public/briefs',out/'data/briefs')
(out/'config.json').write_text(json.dumps({'mode':'pages'},ensure_ascii=False)+'\n')
(out/'.nojekyll').touch()
print('GitHub Pages build:',out)
