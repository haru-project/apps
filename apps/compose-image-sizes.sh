#!/usr/bin/env bash
set -euo pipefail

COMPOSE_FILE="${1:-docker-compose-perception.yaml}"

# 1) Resolve images from the compose file (includes profiles/extends after config resolution)
mapfile -t IMAGES < <(docker compose -f "$COMPOSE_FILE" config --images | sort -u)

if [ ${#IMAGES[@]} -eq 0 ]; then
    echo "No images found in $COMPOSE_FILE" >&2
    exit 1
fi

echo "Images:"
printf "  %s\n" "${IMAGES[@]}"

# 2) Ensure they exist locally (pull; if you build locally, run `docker compose build` instead)
echo "Pulling images..."
for img in "${IMAGES[@]}"; do
    docker pull "$img" >/dev/null
done

# 3) Naïve total = sum of image inspect sizes (bytes)
naive_total=0
for img in "${IMAGES[@]}"; do
    sz="$(docker image inspect "$img" --format '{{.Size}}')"
    naive_total=$((naive_total + sz))
done

# 4) Unique storage ≈ size of a single multi-image save tar
tmp_tar="$(mktemp -t compose-images-XXXXXX.tar)"
trap 'rm -f "$tmp_tar"' EXIT

echo "Creating combined tar (dedupes shared layers)..."
docker image save -o "$tmp_tar" "${IMAGES[@]}"

unique_total="$(stat -c%s "$tmp_tar" 2>/dev/null || stat -f%z "$tmp_tar")"

savings=$((naive_total - unique_total))

echo
echo "Results (bytes):"
echo "  Naïve sum of images:        $naive_total"
echo "  Unique bytes (layer union): $unique_total"
echo "  Savings from layer reuse:   $savings"

# Optional: human-readable
NAIVE="$naive_total" UNIQUE="$unique_total" SAVINGS="$savings" python3 - <<'PY'
import os, sys
# Use safe access to environment variables with defaults
naive=int(os.environ.get("NAIVE", "0"))
unique=int(os.environ.get("UNIQUE", "0"))
savings=int(os.environ.get("SAVINGS", "0"))

def hr(n):
    for u in ["B","KiB","MiB","GiB","TiB"]:
        if n < 1024: return f"{n:.2f} {u}"
        n/=1024
    return f"{n:.2f} PiB"

print("\nHuman-readable:")
print(f"  Naïve sum:  {hr(naive)}")
print(f"  Unique:     {hr(unique)}")
print(f"  Savings:    {hr(savings)}")
PY
