#!/bin/bash

for f in *.py; do
  mpy-cross -march=armv7emsp $f
done
