#!/usr/bin/env python3
"""把 21 张表情图片打包进 assets 分区镜像（配合 kUseImageFaces 图片脸模式）。

用法:
    python scripts/pack_faces.py --base build/generated_assets.bin --faces ./my-faces --out faces-assets.bin

--base   编译生成的 build/generated_assets.bin（里面带字体和语音模型，会原样保留）
--faces  放表情图片的文件夹，文件名必须是 neutral.png / happy.png / sad.png ...（见 README）
--out    输出文件，烧写到 assets 分区（本项目分区表里是 0xa10000）

图片会被居中裁剪并缩放到屏幕大小（默认 320x240），再压成 256 色 PNG，
否则 21 张整屏图放不进约 5.9 MB 的 assets 分区。需要 Pillow: pip install pillow
"""
import argparse
import io
import os
import struct
import sys

from PIL import Image, ImageOps

ENTRY = 44          # name[32] + size(u32) + offset(u32) + width(u16) + height(u16)
MAGIC = b"\x5a\x5a"  # 每个文件数据前的 2 字节标记


def unpack(blob):
    count = struct.unpack("<I", blob[:4])[0]
    data0 = 12 + count * ENTRY
    files = []
    for i in range(count):
        e = blob[12 + i * ENTRY: 12 + (i + 1) * ENTRY]
        name = e[:32].rstrip(b"\0").decode()
        size, offset = struct.unpack("<II", e[32:40])
        files.append((name, blob[data0 + offset + 2: data0 + offset + 2 + size]))
    return files


def pack(files):
    table, body = b"", b""
    for name, data in files:
        table += name.encode().ljust(32, b"\0") + struct.pack("<IIHH", len(data), len(body), 0, 0)
        body += MAGIC + data
    payload = table + body
    return struct.pack("<III", len(files), sum(payload) & 0xFFFF, len(payload)) + payload


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True)
    ap.add_argument("--faces", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, default=320)
    ap.add_argument("--height", type=int, default=240)
    ap.add_argument("--colors", type=int, default=256)
    ap.add_argument("--partition-size", type=lambda s: int(s, 0), default=0x5F0000)
    args = ap.parse_args()

    files = unpack(open(args.base, "rb").read())
    out, missing = [], []
    for name, data in files:
        if name.endswith(".png"):
            src = os.path.join(args.faces, name)
            if not os.path.exists(src):
                missing.append(name)
            else:
                im = ImageOps.fit(Image.open(src).convert("RGB"), (args.width, args.height), Image.LANCZOS)
                im = im.quantize(colors=args.colors, dither=Image.NONE)
                buf = io.BytesIO()
                im.save(buf, "PNG", optimize=True)
                data = buf.getvalue()
        out.append((name, data))
    if missing:
        print("警告：以下表情没有找到对应图片，保留原图：", ", ".join(missing))

    image = pack(out)
    if len(image) > args.partition_size:
        sys.exit(f"打包结果 {len(image)} 字节，超过分区大小 {args.partition_size} 字节，请减小 --colors 或图片尺寸")
    open(args.out, "wb").write(image)
    print(f"已写入 {args.out}：{len(image)} 字节，分区剩余 {args.partition_size - len(image)} 字节")


if __name__ == "__main__":
    main()
