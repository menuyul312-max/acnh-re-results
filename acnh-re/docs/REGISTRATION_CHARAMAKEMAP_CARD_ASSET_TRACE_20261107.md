# ACNH `CharaMakeMap` card asset trace

Date: 7 November 2026. Target: 1.0.0 registration. The BFLYT/BNTX evidence below comes from the supplemental UI archives under `downloads/acnh_additional_romfs_2026-11-02/romfs/Layout`; those archives do not carry a build id, so their relation to 1.0.0 stays open. Full hashes, extracted entry metadata, parser outputs, decoded texture metadata, and PNG hashes are in [machine-readable asset trace](../output/gameplay/registration_charamakemap_card_asset_trace_20261107.json).

## Card pane chain

`CharaMakeMap.bflyt` has four `prt1` children under `N_InOut_01`: `L_Btn_00`, `L_Btn_01`, `L_Btn_02`, and `L_Btn_03`. Each is 562×438 and each names `LCharaMakeMapBtn` as its `part_layout`. Their part is shared; there are no distinct per-card BFLYT or BNTX files in this trace.

`LCharaMakeMapBtn.bflyt` places `L_MapChoice_00` (`part_layout=LMapChoice`) inside `N_Capture_00`; it also has `L_LoadingIcon_00` (`part_layout=LIconLoad`) and a separate 418×418 `P_Capture_00` picture. `LMapChoice.bflyt` contains `P_Map_00` (380×380) under `N_Scissor_00`, an overlay `P_Material_00`, and nested `L_IconOpenSpace_00` (`part_layout=LMapIconOpenSpaceStart`).

## Image vs. card decoration

`P_Capture_00` uses material `P_Capture_00`, whose BNTX texture bindings are `Black_00^r` (8×8) and `Noise+r` (64×64). Those are mask/noise inputs. The nested `P_Map_00` uses material `P_Map_00`, bound to `Capture^t`; the embedded BNTX’s `Capture^t` decodes to a single uniform transparent color at 8×8. It is therefore not a static island preview. The layout exposes a capture-named texture slot, but the supplied files do not establish who writes it at runtime or whether it is replaced by island imagery. That runtime link stays open.

The card part’s UI texture set includes `WorkBenchCardCornerR12^s` and `WorkBenchCardCornerR12Sh^s` for frame corner/shadow materials; `Corner^s` for card base corners; `TexPaper^s`, `MapWave^s`, and `GraSinV^w` for paper/wave/gradient treatments; plus `Black_00^r` and `Noise+r` as material inputs. `LMapChoice` also has `Noise^r`. The open-space marker part uses `FullMapIconMrk01^t` and `MiniMapIconOpenSpc^s`; these are marker/UI graphics. No decoded static texture among the card and nested child BNTX entries is an island thumbnail. The image classification follows BFLYT material indices and BNTX names, dimensions, and decoded contents, not filenames alone.

The parent `CharaMakeMap` BNTX is screen furniture: `LogoNookIncETC^s`, `LogoNookIncJP^s`, `StartHeaderL^s`, `StartHeaderR^s`, `StartPattern^r`, `StartWindowBaseSdw^s`, `StartWindowBase^s`, and `TexPaper^r`.

## 1.0.0 `Param/Layout/CharaMakeMap.byml` bridge check

The available candidate converted record for this check is `analysis/acnh/project/generated/data/static/Param/Layout/CharaMakeMap.json` (workspace-relative, outside this repository), SHA-256 `b6c1cbdf094d07f00ae86c853e12fe07179253c74a556f0bd721a2c1eaf5559e`. Its decoded `XLink` points to `UI_CharaMakeMap` and dialog aliases `/L_Dialog_00`, `L_Dialog_00/L_BtnL`, and `L_Dialog_00/L_BtnR`. There is no per-card part/image path or `cVillage` literal in this record. The raw BYML is not available in the workspace, so its source bytes/hash and the converted record’s game-build provenance could not be independently rechecked.

## Exact sources and conversions

All five supplemental `.zs` archives and their extracted nested SARC entries are enumerated in the JSON. Compressed source hashes:

| Archive | Compressed source SHA-256 |
|---|---|
| `CharaMakeMap.Nin_NX_NVN.zs` | `873d26ca41ba4b982cc96b55daf68adcdc657099be50626266615b3a9f2b6700` |
| `LCharaMakeMapBtn.Nin_NX_NVN.zs` | `04bb82e3cbd7c02109af61f3d76731b1188d32e6d748a044ccb78c5ce397fb34` |
| `LMapChoice.Nin_NX_NVN.zs` | `d53a3adecc2b6a30586f46fa62b3a59dee533110d70e9ccf3c69b68cb6108cc1` |
| `LIconLoad.Nin_NX_NVN.zs` | `c6d26e1baab869f2977509614caa43c79737b1c9efa04778904a9473a92f2fea` |
| `LMapIconOpenSpaceStart.Nin_NX_NVN.zs` | `e22c37ea04173e427c22c2db2f46bd44ebfcce2f91988d8c812f4c36fd0509a1` |

BNTX-to-PNG inventory (full SHA-256 values; the JSON gives every source and output path):

| Archive | Texture / observed role | Size / format | Source BNTX SHA-256 | Converted PNG SHA-256 |
|---|---|---|---|---|
| `CharaMakeMap` | `LogoNookIncETC^s` — screen logo | 428×86 BC4_UNORM | `5d0bae0edd0ed336c6bdb88318ca58b788738c52532a25efd2f67a731a00bb93` | `21e664ffa19e79342991690b27c2d21e6b995c0c59710ab42e32f70c7494e69d` |
| `CharaMakeMap` | `LogoNookIncJP^s` — screen logo | 428×86 BC4_UNORM | `5d0bae0edd0ed336c6bdb88318ca58b788738c52532a25efd2f67a731a00bb93` | `d4659945ddeab9835e50dec758e3ffb570b84fd883aab0b4bc43fea4a87be5e9` |
| `CharaMakeMap` | `StartHeaderL^s` — sheet header | 50×48 BC4_UNORM | `5d0bae0edd0ed336c6bdb88318ca58b788738c52532a25efd2f67a731a00bb93` | `1b2acac4b25519238b1dc45a60664bc73cb5e259ad51d17cc8d1ea4454e3689f` |
| `CharaMakeMap` | `StartHeaderR^s` — sheet header | 50×48 BC4_UNORM | `5d0bae0edd0ed336c6bdb88318ca58b788738c52532a25efd2f67a731a00bb93` | `b5a841560921cac42f94b83d988e43e3bfab58a539b42cc8af21973bf2fc252a` |
| `CharaMakeMap` | `StartPattern^r` — sheet pattern | 200×200 BC4_UNORM | `5d0bae0edd0ed336c6bdb88318ca58b788738c52532a25efd2f67a731a00bb93` | `8634286c80f9e0426e8abb36c60d5e55767f60790bec87299ecce8f7b6513dff` |
| `CharaMakeMap` | `StartWindowBaseSdw^s` — sheet shadow | 60×60 BC4_UNORM | `5d0bae0edd0ed336c6bdb88318ca58b788738c52532a25efd2f67a731a00bb93` | `256c456b4e4abd85e88aa4092f70bbdd75320ebdf6936e27115c22ee1056edcb` |
| `CharaMakeMap` | `StartWindowBase^s` — sheet base | 60×60 BC4_UNORM | `5d0bae0edd0ed336c6bdb88318ca58b788738c52532a25efd2f67a731a00bb93` | `809a1f2bf1788f5381492135c10d7f3a1bb372de5fa461f60a7f29e3f5f71e59` |
| `CharaMakeMap` | `TexPaper^r` — screen paper pattern | 256×256 BC4_UNORM | `5d0bae0edd0ed336c6bdb88318ca58b788738c52532a25efd2f67a731a00bb93` | `727cd70a8b6bfd9254618f19ab5e33db8e50fe09098fcd80769d222b5bb755a5` |
| `LCharaMakeMapBtn` | `Black_00^r` — capture overlay mask | 8×8 BC4_UNORM | `70a859c80fa60ccd45647f4ee4d2e7d952ba25156a721bf592c242cd76808803` | `2f62f422e0729f6b85cbd215464738166844882753b3d5c36014f094eb709947` |
| `LCharaMakeMapBtn` | `Corner^s` — card base corner | 8×8 BC4_UNORM | `70a859c80fa60ccd45647f4ee4d2e7d952ba25156a721bf592c242cd76808803` | `acd56e470ff7b2982e9ce9142cc365a88d787d7815d0c7d003340184c5715982` |
| `LCharaMakeMapBtn` | `GraSinV^w` — card shading/gradient | 64×64 ASTC_4x4_SRGB | `70a859c80fa60ccd45647f4ee4d2e7d952ba25156a721bf592c242cd76808803` | `b2f199e4439468e01a4b6e30e41ba753b2ee157b240b019cf646ce32d1dd0e0a` |
| `LCharaMakeMapBtn` | `MapWave^s` — card wave decoration | 64×32 BC4_UNORM | `70a859c80fa60ccd45647f4ee4d2e7d952ba25156a721bf592c242cd76808803` | `8ca93dd6242623f1cbcf03b1c01e726a94311f48783c17cdfc86c885aa56c865` |
| `LCharaMakeMapBtn` | `Noise+r` — capture overlay noise | 64×64 BC4_UNORM | `70a859c80fa60ccd45647f4ee4d2e7d952ba25156a721bf592c242cd76808803` | `b423f752a62aa056095d8937536043ead227ea49af864fa6b372fd332ccc4dc9` |
| `LCharaMakeMapBtn` | `TexPaper^s` — card paper pattern | 256×256 BC4_UNORM | `70a859c80fa60ccd45647f4ee4d2e7d952ba25156a721bf592c242cd76808803` | `09380388f7a2ffa5f890a0b3edf505fe201505bcef6953fea07e7d3f87e678eb` |
| `LCharaMakeMapBtn` | `WorkBenchCardCornerR12Sh^s` — card frame shadow corner | 24×24 BC4_UNORM | `70a859c80fa60ccd45647f4ee4d2e7d952ba25156a721bf592c242cd76808803` | `494bfd1086bc4e4ab6df2501307a02d2d8f0b89917684525bc9b27e6f7abc07d` |
| `LCharaMakeMapBtn` | `WorkBenchCardCornerR12^s` — card frame corner | 14×14 BC4_UNORM | `70a859c80fa60ccd45647f4ee4d2e7d952ba25156a721bf592c242cd76808803` | `e2357485aeaad73f8424ce4640b82adaf9816be7e78192078081091a40d40af2` |
| `LMapChoice` | `Capture^t` — map pane capture slot; transparent 8×8 placeholder | 8×8 BC5_UNORM | `6cc500513685c399c42dc3ec3cdf8f68c8a2611aa76af3afeb3bd203da2648b9` | `58014df8c2e6a72b5323bfbb0a565ffb403ce1008215afbda789624c5b0f9ea7` |
| `LMapChoice` | `Noise^r` — map pane overlay noise | 64×64 BC4_UNORM | `6cc500513685c399c42dc3ec3cdf8f68c8a2611aa76af3afeb3bd203da2648b9` | `e8a3e224eb7a27823434fcd48e05103d4ce2fec7b63376329ed19722b4c980b5` |
| `LIconLoad` | `MaruBlur^s` — loading icon blur | 8×8 BC4_UNORM | `661709c684e95f38eabe20b71360e13ec3f90d93d29634e4ed6bf000c2ccbebe` | `e87d47141238ca2a95cbe9a44d2531147cd98d3f4054e1d8867e322ae918cca7` |
| `LIconLoad` | `White_00^r` — loading icon white fill | 8×8 BC4_UNORM | `661709c684e95f38eabe20b71360e13ec3f90d93d29634e4ed6bf000c2ccbebe` | `67415ef8853df4544712f37a2e99a1b85f22f01897544226b1daf1b1198af35b` |
| `LMapIconOpenSpaceStart` | `FullMapIconMrk01^t` — open-space map marker | 64×64 BC5_UNORM | `6a4c069a9a401335616d3a349ea4d76093509a8fed065e5777147ef91d64a953` | `23bfae42fec40d884dc89ad810cdf38767f726de2139707277d2680f7f1edffc` |
| `LMapIconOpenSpaceStart` | `MiniMapIconOpenSpc^s` — open-space minimap icon | 38×32 BC4_UNORM | `6a4c069a9a401335616d3a349ea4d76093509a8fed065e5777147ef91d64a953` | `4ce4d424e286e6a3c958284ccfcae369356661a3a21bf9a12dee2dec6280ca36` |

The five parsed BFLYT JSON projections and 22 decoded PNGs are workspace support outputs, kept outside this deliverable repository at `analysis/acnh/CharaMakeMap_asset_trace/`. The JSON records each source entry, converter, output path, and full SHA-256. To regenerate them from `/workspace` (requires the supplemental archives and the `acnh_rip` tools tree at the cited paths):

```sh
gcc -O2 -o /tmp/acnh_ui_texdec /workspace/downloads/ACNH_island_RE/ACNH_island_RE/C_reverse/tools/acnh_rip/native/texdec.c -lm
python3 - <<'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, "/workspace/downloads/ACNH_island_RE/ACNH_island_RE/C_reverse/tools")
from acnh_rip.formats import bflyt, compression, sarc
from acnh_rip.exporters import models
models.TEXDEC = Path("/tmp/acnh_ui_texdec")
romfs = Path("/workspace/downloads/acnh_additional_romfs_2026-11-02/romfs/Layout")
out = Path("/workspace/analysis/acnh/CharaMakeMap_asset_trace")
stems = ["CharaMakeMap", "LCharaMakeMapBtn", "LMapChoice", "LIconLoad", "LMapIconOpenSpaceStart"]
for stem in stems:
    src = romfs / (stem + ".Nin_NX_NVN.zs")
    outer = sarc.read_sarc(compression.read_file(src))
    for archive_bytes in outer.values():
        if archive_bytes[:4] != b"SARC":
            continue
        for name, data in sarc.read_sarc(archive_bytes).items():
            if data[:4] == b"FLYT":
                target = out / "converted_layouts" / stem / (Path(name).stem + ".json")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(json.dumps(bflyt.read_bflyt(data), ensure_ascii=False, separators=(",", ":")))
            elif data[:4] == b"BNTX":
                models._decode_textures(data, out / "converted_textures" / stem, {"textures": [], "errors": []})
PY
sha256sum /workspace/analysis/acnh/CharaMakeMap_asset_trace/converted_layouts/*/*.json /workspace/analysis/acnh/CharaMakeMap_asset_trace/converted_textures/*/*.png
```

`texdec.c` includes `astc.h` from the same directory. `_decode_textures` parses BNTX metadata with `formats/bntx.py` and exports mip 0 / layer 0 through the compiled decoder. Conversion-tool source hashes are recorded in the linked JSON. No decoded images or parsed layout projections were copied into this repository.

The static UI trace has no established edge to the native `cVillage` result context. The separate [cVillage result-context follow-up](REGISTRATION_CVILLAGE_CONTEXT_FOLLOWUP_20261107.md) and [its JSON trace](../output/gameplay/registration_c_village_context_followup_20261107.json) find a transient four-option result index, but leave its action/page/controller producer and option-to-preset mapping open. No path in the available `Param/Layout/CharaMakeMap.json` joins `L_Btn_00..03` to that native store. The supplemental archive release id and compatibility with 1.0.0 are also open; these layouts do not identify the runtime producer or version compatibility of the capture slot.
