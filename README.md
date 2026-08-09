# XTranscoder

XTranscoder is a dependency-free converter for one-dimensional powder X-ray diffraction (XRD) data. It automatically identifies the formats represented in `samples/`, reads them into a shared `(2θ, intensity)` model, and exports standard `0.csv` by default. A GitHub Pages web app provides in-browser conversion and previews.

## Supported formats

| ID | Format | Read | Write from CLI / website |
| --- | --- | --- | --- |
| 0 | Headerless two-column CSV | ✓ | ✓ |
| 1 | PANalytical XRDML | ✓ | ✓ |
| 2 | Binary RAW (sample layout) | ✓ | — |
| 3 | CSV with `[Scan points]` | ✓ | ✓ |
| 4 | CSV with `2_theta,Intensity` header | ✓ | ✓ |
| 5 | DAT | ✓ | ✓ |
| 6 | Space-delimited XY | ✓ | ✓ |
| 7 | RAW4 text TXT | ✓ | ✓ |

`2.raw` is a proprietary binary container. XTranscoder reads the data block used by the supplied sample, but does not write a vendor-compatible binary RAW file because there is no reliable general binary layout to generate. If the RAW file does not expose usable scan coordinates, its exported x-axis is the point index; verify the 2θ calibration in the acquisition software. The remaining formats (0, 1, 3, 4, 5, 6, and 7) can be converted between one another.

## Install and use from the command line

Python 3.10 or later is required. No third-party runtime packages are needed.

```bash
python -m pip install -e .

# Automatically detect the input and write standard 0.csv.
xtranscoder samples/1.xrdml result.csv

# Write another supported text format.
xtranscoder samples/5.dat result.xy --format 6.xy
```

The package API is equally small:

```python
from xtranscoder import read, write

pattern = read("samples/7.txt")  # format is detected automatically
write(pattern, "result.csv")     # 0.csv is the default
```
