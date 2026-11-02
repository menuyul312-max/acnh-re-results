#!/usr/bin/env python3
"""Publish bounded native instruction evidence for the named semantic findings."""
import hashlib
from pathlib import Path
from native_image import Image
from reverse_corpus import dump

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'output'


def build():
    im=Image()
    regions={'terrain_copy':(0x542db0,0x17c),'terrain_height':(0xf52860,0x14),
        'terrain_model_format':(0x543340,0x6c),'recipe_slots':(0xedac50,0x1300),
        'curve_Hermit2D':(0x19ab390,0x110),'curve_Hermit2DSmooth':(0x19ab540,0x120),
        'C1_entry':(0x21e21e0,0x10),'C1_recursive':(0x21e21f0,0x300),
        'ExitFlowchart_start':(0x447060,0x474),'ExitFlowchart_predicate':(0x4474e0,0x134),
        'parameter_descriptor_formatter_s32':(0x67770,0x3c),
        'parameter_descriptor_hash':(0x1c87110,0xa0),'parameter_array_formatter':(0xd47710,0x18),
        'crc32_cstring':(0x19ab050,0x2c),'item_field_preset_constructor':(0x555e20,0x330),
        'item_room_placement_constructor':(0xd467b0,0x330),
        'item_copy':(0xf589b0,0x24),'item_assignment':(0xf589e0,0x24),
        'item_empty_reset':(0x1a6560,0x10),'item_lookup_id':(0xf58a90,0x54),
        'item_wrapping_paper':(0xab4420,0x28),'item_extension_coordinates':(0xf59f70,0x2c),
        'typed_array_bool_formatter':(0x10c1740,0xa0),'typed_array_s32_formatter':(0x9393a0,0x30),
        'byml_data_normalize':(0x1ef5cf0,0x40),'byml_dictionary_index_unchecked':(0x1ef63d0,0xd0),
        'byml_dictionary_index_checked':(0x1ef6510,0xb0),
        'stage_key_init_suffix':(0xffa3b0,0x280),'stage_key_getter':(0xffa690,0x40),
        'stage_projection':(0xfeeeb0,0x150),'stage_direction_interpolation':(0x1cb70,0xe0),
        'actor_type_init_suffix':(0x61ee0,0x970),'actor_type_hash_lookup':(0x628b0,0x80),
        'human_signed_animation_selector':(0x7d16c4,0x28),
        'flag_reset_policy':(0xf54530,0x90),'native_rng_pure_helpers':(0x19aa040,0x160),
        'weather_normal_day_selector':(0xfdd9b0,0x1a8),'weather_calendar_lookup':(0x201dc0,0x188),
        'weather_date_normalizer':(0x1fbc00,0x70),'weather_hemisphere_container':(0x206ef0,0x50),
        'npc_voice_binding_block':(0x160b144,0x910),
        'bcsv_relative_metadata_pointer':(0x1665e50,0x44)}
    # Preserve the loader's compare/select surrounding the real limit getter call.
    code=im.disasm(0x558f40,0x900)
    call=next(i for i,ins in enumerate(code) if ins.mnemonic=='bl' and ins.op_str=='#0x547520')
    regions['terrain_variant_validation']=(code[max(0,call-10)].address,0xf0)
    assert im.cstring(0x2996f6e)=='%s_%d'
    result={'elf_sha256':hashlib.sha256(im.data).hexdigest(),'address_space':'ELF VA',
        'note':'Bounded instruction regions; some regions may include adjacent code, not asserted function extents.',
        'model_format':{'va':'0x2996f6e','string':'%s_%d'},'regions':{}}
    for name,(va,size) in regions.items():
        p=OUT/'binary/evidence'/f'{name}.asm';p.parent.mkdir(parents=True,exist_ok=True)
        instructions=im.disasm(va,size)
        p.write_text('\n'.join(f'{i.address:08x} {i.bytes.hex():8s} {i.mnemonic:8s} {i.op_str}' for i in instructions)+'\n')
        result['regions'][name]={'start_va':hex(va),'bytes_requested':size,
            'raw_sha256':hashlib.sha256(im.read(va,size)).hexdigest(),'assembly':str(p.relative_to(OUT))}
    dump(OUT/'binary/critical_evidence.json',result)
    print('native evidence regions',len(regions))


if __name__=='__main__':build()
