"""Render the app's original layered-page mark at Splunk menu resolutions."""
from pathlib import Path
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[1]/'splunk_actionstack'/'static'
ROOT.mkdir(exist_ok=True)
scale=12
canvas=Image.new('RGBA',(36*scale,36*scale))
d=ImageDraw.Draw(canvas)
def pts(points):return [(int(x*scale),int(y*scale)) for x,y in points]
d.rounded_rectangle((scale,scale,35*scale,35*scale),radius=9*scale,fill='#141b28',outline='#58627d',width=scale)
for y,color in [(23,'#73d2de'),(18,'#afa8ed')]:
 d.line(pts([(7,y),(18,y+6),(29,y)]),fill=color,width=2*scale,joint='curve')
d.polygon(pts([(7,13),(18,7),(29,13),(18,19)]),fill='#c5b3f1')
d.line(pts([(7,13),(18,19),(29,13)]),fill='#dcddff',width=scale)
for name,size in [('appIcon.png',36),('appIcon_2x.png',72),('appIconAlt.png',36),('appIconAlt_2x.png',72)]:
 canvas.resize((size,size),Image.Resampling.LANCZOS).save(ROOT/name)
print(ROOT)
