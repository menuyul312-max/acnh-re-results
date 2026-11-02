#!/usr/bin/env python3
"""Preserve the available BC4 textures as linear DDS, with original channel maps.

The address formula follows the Tegra GOB layout also documented by the supplied
texdec.c. Original tiled padding remains in the provenance blobs.
"""
import hashlib
import json
from pathlib import Path
import struct

from reverse_corpus import dump

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT/'output'


def address(x,y,width_bytes,bh):
    wg=(width_bytes+63)//64
    return ((y//(8*bh))*512*bh*wg+(x//64)*512*bh+((y%(8*bh))//8)*512
            +((x%64)//32)*256+((y%8)//2)*64+((x%32)//16)*32+(y%2)*16+x%16)


def build():
    manifest=json.loads((OUT/'manifest.json').read_text())['entries']
    entry=next(e for e in manifest if e['format']=='BNTX')
    textures=json.loads((OUT/entry['decoded']).read_text())['data']['textures']
    result=[]
    for texture in textures:
        assert texture['format_name']=='BC4_UNORM' and texture['array_count']==1 and texture['depth']==1
        payload, records = bytearray(), []
        for mip in texture['mips']:
            raw=(OUT/mip['raw']['$blob']).read_bytes()
            wb,hb=(mip['width']+3)//4,(mip['height']+3)//4
            bh=1<<texture['block_height_log2']
            while bh>1 and hb<=bh*4:bh//=2
            used=set();linear=bytearray(wb*hb*8)
            for y in range(hb):
                for x in range(wb):
                    source=address(x*8,y,wb*8,bh)
                    assert source%8==0 and source+8<=len(raw) and source not in used
                    used.add(source)
                    dest=(y*wb+x)*8
                    linear[dest:dest+8]=raw[source:source+8]
            # Reassemble used tiles in their original positions; retain untouched
            # source padding and require byte equality with the complete source mip.
            restored=bytearray(raw)
            for y in range(hb):
                for x in range(wb):
                    source=address(x*8,y,wb*8,bh);dest=(y*wb+x)*8
                    restored[source:source+8]=linear[dest:dest+8]
            assert restored==raw
            records.append({'level':mip['level'],'width':mip['width'],'height':mip['height'],
                'effective_block_height':bh,'linear_bytes':len(linear),'raw':mip['raw'],
                'linear_sha256':hashlib.sha256(linear).hexdigest(),'tile_blocks_checked':len(used),
                'padding_bytes_retained_only_in_raw':len(raw)-len(linear)})
            payload+=linear
        count=texture['mip_count'];multi=count>1
        words=[124,0x81007|(0x20000 if multi else 0),texture['height'],texture['width'],
            records[0]['linear_bytes'],0,count]+[0]*11
        header=struct.pack('<18I',*words)+struct.pack('<II4s5I',32,4,b'DX10',0,0,0,0,0)
        header+=struct.pack('<5I',0x1000|(0x400008 if multi else 0),0,0,0,0)
        assert len(header)==124
        dds=b'DDS '+header+struct.pack('<5I',80,3,0,1,0)+payload
        dest=OUT/'environment/textures'/f"{texture['name']}.dds"
        dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(dds)
        result.append({'name':texture['name'],'source_id':entry['id'],'format':'DDS DX10 BC4_UNORM',
            'dds':str(dest.relative_to(OUT)),'sha256':hashlib.sha256(dds).hexdigest(),
            'source_channel_sources':texture['channel_sources'],
            'channel_note':'DDS preserves the red BC4 payload. Apply original BNTX channel sources separately; 2 means R.',
            'mips':records,'validation':'bounds, unique block addresses, full used-block retile equality'})
    dump(OUT/'environment/textures.json',result)
    print(json.dumps({'textures':len(result),'mips':sum(len(t['mips']) for t in result),
        'blocks_checked':sum(m['tile_blocks_checked'] for t in result for m in t['mips'])},indent=2))


if __name__ == '__main__':build()
