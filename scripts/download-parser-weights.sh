#!/bin/bash

ORIGINAL_PWD=$PWD
CURRENT_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd ${CURRENT_SCRIPT_DIR}/../parser/OmniParserFork/
. download_parser_weights.sh
cd $ORIGINAL_PWD
