# To install just on a per-project basis
# 1. Activate your virtual environemnt
# 2. uv add --dev rust-just
# 3. Use just within the activated environment

drive_uuid := "77688511-78c5-4de3-9108-b631ff823ef4"
user :=  file_stem(home_dir())
def_drive := join("/media", user, drive_uuid)
project := file_stem(justfile_dir())
local_env := join(justfile_dir(), ".env")


# list all recipes
default:
    just --list

# Install tools globally
tools:
    uv tool install twine
    uv tool install ruff

# Add conveniente development dependencies
dev:
    uv add --dev pytest

# Build the package
build:
    rm -fr dist/*
    uv build

# Publish the package to PyPi
publish pkg="zptess": build
    twine upload -r pypi dist/*
    uv run --no-project --with {{pkg}} --refresh-package {{pkg}} \
        -- python -c "from {{pkg}} import __version__; print(__version__)"

# Publish to Test PyPi server
test-publish pkg="zptess": build
    twine upload --verbose -r testpypi dist/*
    uv run --no-project  --with {{pkg}} --refresh-package {{pkg}} \
        --index-url https://test.pypi.org/simple/ \
        --extra-index-url https://pypi.org/simple/ \
        -- python -c "from {{pkg}} import __version__; print(__version__)"

# Adds lica source library as dependency. 'version' may be a tag or branch
lica-dev version="main":
    #!/usr/bin/env bash
    set -exuo pipefail
    echo "Removing previous LICA dependency"
    uv add aiohttp pyserial-asyncio aioserial tabulate
    uv remove lica || echo "Ignoring non existing LICA library";
    if [[ "{{ version }}" =~ [0-9]+\.[0-9]+\.[0-9]+ ]]; then
        echo "Adding LICA source library --tag {{ version }}"; 
        uv add git+https://github.com/guaix-ucm/lica --tag {{ version }};
    else
        echo "Adding LICA source library --branch {{ version }}";
        uv add git+https://github.com/guaix-ucm/lica --branch {{ version }};
    fi

# Adds lica release library as dependency with a given version
lica-rel version="":
    #!/usr/bin/env bash
    set -exuo pipefail
    echo "Removing previous LICA dependency"
    uv remove lica || echo "Ignoring non existing LICA library";
    echo "Adding LICA library {{ version }}";
    uv add --refresh-package lica lica[photometer,tabular] {{ version }};
    uv remove aiohttp aioserial pyserial-asyncio tabulate


# Backup .env to storage unit
env-bak drive=def_drive: (check_mnt drive) (env-backup join(drive, "env", project))

# Restore .env from storage unit
env-rst drive=def_drive: (check_mnt drive) (env-restore join(drive, "env", project))

# Restore a fresh, unmigrated ZPTESS database
db-anew drive=def_drive: (check_mnt drive) (db-restore)

# Starts a new database export migration cycle   
anew folder="migra" verbose="": db-anew
    #!/usr/bin/env bash
    set -exuo pipefail
    uv sync --reinstall
    uv run zp-db-fix-src
    test -d {{ folder }} || mkdir {{ folder }}
    uv run zp-db-schema --console {{ verbose }}
    uv run zp-db-extract --console {{ verbose }} all --output-dir {{ folder }}

# Starts a new database import migration cycle   
aload stage="summary" folder="migra":
    #!/usr/bin/env bash
    set -exuo pipefail
    test -d {{ folder }} || mkdir {{folder}}
    uv run zp-db-loader --console config --input-dir {{folder}}
    uv run zp-db-loader --console batch --input-dir {{folder}}
    if [ "{{stage}}" == "photometer" ]; then
        uv run zp-db-loader --console photometer --input-dir {{folder}}
    elif [ "{{stage}}" == "summary" ]; then
        uv run zp-db-loader --console photometer --input-dir {{folder}}
        uv run zp-db-loader --console summary --input-dir {{folder}}
    elif [ "{{stage}}" == "rounds" ]; then
        uv run zp-db-loader --console photometer --input-dir {{folder}}
        uv run zp-db-loader --console summary --input-dir {{folder}}
        uv run zp-db-loader --console rounds --input-dir {{folder}}
    elif [ "{{stage}}" == "samples" ]; then
        uv run zp-db-loader --console photometer --input-dir {{folder}}
        uv run zp-db-loader --console summary --input-dir {{folder}}
        uv run zp-db-loader --console rounds --input-dir {{folder}}
        uv run zp-db-loader --console samples --input-dir {{folder}}
    else
        echo "No known stage"
        exit 1
    fi

# ========================= #
# QUCK COMMAND LINE TESTING #
# ========================= #

# Writes new zero point to photometer
write zp verbose="" trace="":
    #!/usr/bin/env bash
    set -euxo pipefail
    uv run zp-write --console {{verbose}} {{trace}} test -z {{zp}}

# Reads test/ref/both photometers
read verbose="" trace="" which="test" N="10" :
    #!/usr/bin/env bash
    set -euxo pipefail
    uv run zp-read --console {{verbose}} {{trace}} {{which}} -N {{N}}

# Calibrate photometer
calib verbose="" trace="" persist="":
    #!/usr/bin/env bash
    set -euxo pipefail
    cp zptess.db zptess-prudb.db
    uv run zp-calib --console {{verbose}} {{trace}} test -b 9 -R 3 -P 5 {{persist}}

# Open a new batch
open  verbose="" trace="":
    #!/usr/bin/env bash
    set -euxo pipefail
    uv run zp-begin --console {{verbose}} {{trace}}

# Close current open batch
close  verbose="" trace="":
    #!/usr/bin/env bash
    set -euxo pipefail
    uv run zp-end --console {{verbose}} {{trace}}

# Close current open batch
purge  verbose="" trace="":
    #!/usr/bin/env bash
    set -euxo pipefail
    uv run zp-purge --console {{verbose}} {{trace}}

# Close current open batch
orphan  verbose="" trace="":
    #!/usr/bin/env bash
    set -euxo pipefail
    uv run zp-orphan --console {{verbose}} {{trace}}

# Close current open batch
view  verbose="" trace="":
    #!/usr/bin/env bash
    set -euxo pipefail
    uv run zp-view --console {{verbose}} {{trace}}


# =======================================================================

[private]
db-restore:
    #!/usr/bin/env bash
    set -exuo pipefail
    cp {{ def_drive }}/zptess/zptess-20250121.db zptess.prod.db
    

[private]
check_mnt mnt:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -d  {{ mnt }} ]]; then
        echo "Drive not mounted: {{ mnt }}"
        exit 1 
    fi

[private]
env-backup bak_dir:
    #!/usr/bin/env bash
    set -exuo pipefail
    if [[ ! -f  {{ local_env }} ]]; then
        echo "Can't backup: {{ local_env }} doesn't exists"
        exit 1 
    fi
    mkdir -p {{ bak_dir }}
    cp {{ local_env }} {{ bak_dir }}
    cp zptess.prod.db {{ bak_dir }}
    cp zptess.db {{ bak_dir }}
  
[private]
env-restore bak_dir:
    #!/usr/bin/env bash
    set -euxo pipefail
    if [[ ! -f  {{ bak_dir }}/.env ]]; then
        echo "Can't restore: {{ bak_dir }}/.env doesn't exists"
        exit 1 
    fi
    cp {{ bak_dir }}/.env {{ local_env }}
    cp {{ bak_dir }}/zptess.prod.db .
    cp {{ bak_dir }}/zptess.db .
