#!/usr/bin/env python3
"""Собирает то, что сервер раздаёт ученическим компьютерам (папка kurs/client/dist):

  kurs-panel.vsix   панель VS Code (обычный zip, собирается без Node и npm)
  kurs_check.py     проверка заданий
  kurs_start.py     запуск курса на компьютере ученика
  manifest.json     версия и контрольная сумма панели

  python3 kurs/client/build.py
Сервер вызывает сборку сам при запуске, руками это нужно только для проверки.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
KURS = os.path.dirname(HERE)
EXT = os.path.join(KURS, "vscode")
DIST = os.path.join(HERE, "dist")
CHECKER = os.path.join(KURS, "checker", "kurs_check.py")
EXT_FILES = ["package.json", "extension.js", "lib", "media", "snippets"]

CONTENT_TYPES = """<?xml version="1.0" encoding="utf-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension=".json" ContentType="application/json"/>
<Default Extension=".js" ContentType="application/javascript"/>
<Default Extension=".css" ContentType="text/css"/>
<Default Extension=".html" ContentType="text/html"/>
<Default Extension=".svg" ContentType="image/svg+xml"/>
<Default Extension=".py" ContentType="text/plain"/>
<Default Extension=".vsixmanifest" ContentType="text/xml"/>
</Types>
"""


def manifest_xml(pkg: dict) -> str:
    return f"""<?xml version="1.0" encoding="utf-8"?>
<PackageManifest Version="2.0.0" xmlns="http://schemas.microsoft.com/developer/vsx-schema/2011" xmlns:d="http://schemas.microsoft.com/developer/vsx-schema-design/2011">
  <Metadata>
    <Identity Language="en-US" Id="{pkg['name']}" Version="{pkg['version']}" Publisher="{pkg['publisher']}"/>
    <DisplayName>{pkg['displayName']}</DisplayName>
    <Description xml:space="preserve">{pkg['description']}</Description>
    <Categories>Education</Categories>
    <GalleryFlags>Public</GalleryFlags>
    <Properties>
      <Property Id="Microsoft.VisualStudio.Code.Engine" Value="{pkg['engines']['vscode']}"/>
      <Property Id="Microsoft.VisualStudio.Code.ExtensionDependencies" Value=""/>
      <Property Id="Microsoft.VisualStudio.Code.ExtensionPack" Value=""/>
      <Property Id="Microsoft.VisualStudio.Code.ExtensionKind" Value="workspace"/>
      <Property Id="Microsoft.VisualStudio.Code.LocalizedLanguages" Value=""/>
    </Properties>
  </Metadata>
  <Installation>
    <InstallationTarget Id="Microsoft.VisualStudio.Code"/>
  </Installation>
  <Dependencies/>
  <Assets>
    <Asset Type="Microsoft.VisualStudio.Code.Manifest" Path="extension/package.json" Addressable="true"/>
  </Assets>
</PackageManifest>
"""


def _walk(rel: str):
    full = os.path.join(EXT, rel)
    if os.path.isfile(full):
        yield rel
        return
    for d, _, files in os.walk(full):
        for f in sorted(files):
            if f.startswith(".") or f.endswith(".map"):
                continue
            yield os.path.relpath(os.path.join(d, f), EXT)


def build() -> dict:
    with open(os.path.join(EXT, "package.json"), encoding="utf-8") as fh:
        pkg = json.load(fh)
    os.makedirs(DIST, exist_ok=True)
    vsix = os.path.join(DIST, "kurs-panel.vsix")
    tmp = vsix + ".tmp"
    fixed = (2026, 1, 1, 0, 0, 0)   # одинаковое время в архиве: одинаковые исходники → одинаковый файл
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        def add(name: str, data: bytes):
            z.writestr(zipfile.ZipInfo(name, fixed), data, zipfile.ZIP_DEFLATED)
        add("[Content_Types].xml", CONTENT_TYPES.encode())
        add("extension.vsixmanifest", manifest_xml(pkg).encode())
        for top in EXT_FILES:
            for rel in _walk(top):
                with open(os.path.join(EXT, rel), "rb") as fh:
                    add("extension/" + rel.replace(os.sep, "/"), fh.read())
        with open(CHECKER, "rb") as fh:
            add("extension/bundled/kurs_check.py", fh.read())
    os.replace(tmp, vsix)
    shutil.copy(CHECKER, os.path.join(DIST, "kurs_check.py"))
    shutil.copy(os.path.join(HERE, "kurs_start.py"), os.path.join(DIST, "kurs_start.py"))
    with open(vsix, "rb") as fh:
        sha = hashlib.sha256(fh.read()).hexdigest()
    man = {"version": pkg["version"], "vsix": "kurs-panel.vsix", "sha256": sha, "extension_id": f"{pkg['publisher']}.{pkg['name']}"}
    with open(os.path.join(DIST, "manifest.json"), "w", encoding="utf-8") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=2)
    return man


if __name__ == "__main__":
    m = build()
    print(f"Готово: {DIST}  (панель {m['version']}, sha256 {m['sha256'][:12]}…)")
