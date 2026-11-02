#!/bin/bash
# Fetch the film's JavaScript libraries at the versions it was built with, and check each file
# against the copy that rendered the film (SHA-256). Run from media/launch-film/.
set -euo pipefail
cd "$(dirname "$0")/.."

fetch() {  # url  destination  sha256
  mkdir -p "$(dirname "$2")"
  curl -fsSL "$1" -o "$2.tmp"
  got=$(shasum -a 256 "$2.tmp" | cut -d' ' -f1)
  if [ "$got" != "$3" ]; then
    rm -f "$2.tmp"
    echo "checksum mismatch for $1" >&2
    exit 1
  fi
  mv "$2.tmp" "$2"
  echo "ok  $2"
}

GSAP=https://cdn.jsdelivr.net/npm/gsap@3.14.2
THREE=https://cdn.jsdelivr.net/npm/three@0.186.0

fetch "$GSAP/dist/gsap.min.js" assets/vendor/gsap.min.js \
  c174bfce53a729418d57a8ad8625e7247c793a22fef8e2851e3cfa3de9cd8280
fetch "$THREE/build/three.module.js" stage/vendor/three.module.js \
  9052042d676cb0fdc1ddfefe193053f34b7ac0513a616fdac4535d49987812ea
fetch "$THREE/build/three.core.js" stage/vendor/three.core.js \
  9edde002b066a9a05676a6127f67735b62baf399bdea529f2f7e31657da769e6
fetch "$THREE/examples/jsm/loaders/GLTFLoader.js" stage/vendor/jsm/loaders/GLTFLoader.js \
  131c0f78c01d19368ae495caa65b3adaa10487810a36a05bb5901b769a35ac16
fetch "$THREE/examples/jsm/environments/RoomEnvironment.js" stage/vendor/jsm/environments/RoomEnvironment.js \
  55f466192cc84298755a424c5e040345006b2ee1455589b3b54126c2ea4123f4
fetch "$THREE/examples/jsm/utils/BufferGeometryUtils.js" stage/vendor/jsm/utils/BufferGeometryUtils.js \
  9fb63427ce6641fa14fd0baff9cc4d1b5f9c3d85fd084bf2e90e803c44ec1797
fetch "$THREE/examples/jsm/utils/SkeletonUtils.js" stage/vendor/jsm/utils/SkeletonUtils.js \
  b1632a703206c3d830de9fcbe515696770d04b71a15ee6b50afa6d2c3298c86f
fetch "$THREE/LICENSE" stage/vendor/THREE-LICENSE \
  8b378ebe60e2fe500158cb0ac71cb5e8b7d92953c2abcc63a0eb90499653b5bc
