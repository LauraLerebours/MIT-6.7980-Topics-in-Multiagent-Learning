"""Compare rendered DOM blocks, ignoring vertical movement caused by insertions."""
from difflib import SequenceMatcher
from pathlib import Path
import json

from PIL import Image, ImageChops, ImageDraw


def crop(image, block):
    return image.crop((0, max(0, round(block['top'])), image.width,
                       min(image.height, max(round(block['top']) + 1, round(block['bottom'])))))


def differs(a, b):
    if abs(a.width - b.width) > 1 or abs(a.height - b.height) > 2:
        return True
    b = b.resize(a.size)
    # Subpixel rasterization can shift with the vertical position of an unchanged block.
    delta = ImageChops.difference(a.convert('RGB'), b.convert('RGB'))
    changed = delta.convert('L').point(lambda x: 255 if x > 35 else 0).histogram()[255]
    return changed / max(1, a.width * a.height) > .012


def changed_blocks(left, right, old, new):
    a, b = left['blocks'], right['blocks']
    changes = []
    matcher = SequenceMatcher(None, [x['key'] for x in a], [x['key'] for x in b], autojunk=False)
    for tag, i, j, k, l in matcher.get_opcodes():
        if tag == 'equal':
            for ai, bi in zip(range(i, j), range(k, l)):
                if a[ai]['styles'] != b[bi]['styles'] or differs(crop(old, a[ai]), crop(new, b[bi])):
                    changes.append((ai, ai+1, bi, bi+1))
        else:
            # Do not call unchanged content a deletion merely because its order changed.
            if tag in ('delete', 'insert'):
                source, other = (a[i:j], b) if tag == 'delete' else (b[k:l], a)
                source_image, other_image = (old, new) if tag == 'delete' else (new, old)
                if all(any(x['key'] == y['key'] and x['styles'] == y['styles']
                           and not differs(crop(source_image, x), crop(other_image, y))
                           for y in other) for x in source):
                    continue
            changes.append((i, j, k, l))
    merged = []
    for i, j, k, l in changes:
        if merged and i <= merged[-1][1]+1 and k <= merged[-1][3]+1:
            p, q, r, s = merged.pop()
            merged.append((p, max(q,j), r, max(s,l)))
        else:
            merged.append((i,j,k,l))
    return merged


def strip(image, blocks, start, end):
    if start == end:
        return None
    return image.crop((0, max(0, int(blocks[start]['top'])-3), image.width,
                       min(image.height, int(blocks[end-1]['bottom'])+4)))


def panels(left, right, output, stem, metadata):
    height = 1450
    count = max(1, *((image.height+height-1)//height for image in (left,right) if image))
    result = []
    for part in range(count):
        a = left.crop((0,part*height,left.width,min(left.height,(part+1)*height))) if left and part*height<left.height else None
        b = right.crop((0,part*height,right.width,min(right.height,(part+1)*height))) if right and part*height<right.height else None
        # Continuations without an old/new counterpart use one column.
        columns = [(a,'BEFORE','#b42332'),(b,'AFTER','#197539')]
        columns = [x for x in columns if x[0]]
        canvas = Image.new('RGB',(sum(x[0].width for x in columns)+12*(len(columns)+1), max(x[0].height for x in columns)+46),'#e9eef3')
        draw = ImageDraw.Draw(canvas)
        x = 12
        for image,label,color in columns:
            draw.text((x,12),f'{label} | {metadata["viewport"]}px | part {part+1}/{count}',fill=color)
            canvas.paste(image,(x,34))
            x += image.width+12
        name = f'{stem}-{part+1}.png'
        canvas.save(output/name)
        result.append(dict(file=name,**metadata))
    return result


def compare(browser_folder, output):
    data = json.loads((browser_folder/'browser.json').read_text())
    pages = {(p['side'],p['page'],p['viewport']):p for p in data['pages']}
    regions=[]
    for page,width in sorted({(p['page'],p['viewport']) for p in data['pages']}):
        left = pages.get(('before',page,width),dict(blocks=[]))
        right = pages.get(('after',page,width),dict(blocks=[]))
        old = Image.open(browser_folder/left['image']).convert('RGB') if 'image' in left else Image.new('RGB',(width,1),'white')
        new = Image.open(browser_folder/right['image']).convert('RGB') if 'image' in right else Image.new('RGB',(width,1),'white')
        for n,(i,j,k,l) in enumerate(changed_blocks(left,right,old,new)):
            # Include one preceding/following block. Do not repeat it in continuation panels.
            a=strip(old,left['blocks'],max(0,i-1),min(len(left['blocks']),j+1))
            b=strip(new,right['blocks'],max(0,k-1),min(len(right['blocks']),l+1))
            regions.extend(panels(a,b,output,f'{Path(page).stem}-{width}-{n+1}',dict(page=page,viewport=width)))
            if len(regions)>=120:
                return regions,True
    return regions,False
