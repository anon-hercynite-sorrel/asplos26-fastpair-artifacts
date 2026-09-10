# /// script
# requires-python = ">=3.9"
# dependencies = ["matplotlib", "numpy"]
# ///
"""Render the accepted five-component Windows boost figure.
Raw evidence is validated before rendering; see experiments/pipes/README.md.
"""
import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, help='Output directory (default figures/out).')
    args = ap.parse_args()
    import common as C
    from pipes_data import load, CAMPAIGN
    here = CAMPAIGN
    source = Path(C.__file__)
    if args.output:
        C.OUTDIR = args.output.resolve()
        C.ROOT = C.OUTDIR.parent
    C.OUTDIR.mkdir(parents=True, exist_ok=True)
    accepted, directions = load()
    rows = {c['chip']: c for c in directions['cells'] if 'winner' in c['roles']}
    order = C.DEVICE_ORDER
    assert set(rows) == set(order)
    metrics = {}
    for chip in order:
        assert accepted[chip]['status'] == 'validated'
        cell = next(c for c in accepted[chip]['cells'] if 'winner' in c['roles'])
        assert rows[chip]['kernel'] == cell['kernel']
        metrics[chip] = cell['metrics_mean']
        assert math.isclose(sum(rows[chip]['peak_points'].values()), metrics[chip]['l1_elapsed_pct'], abs_tol=1e-9)
    import numpy as np
    plt = C.apply_theme()
    fig, ax = plt.subplots(figsize=(3.4, 1.95))
    x = np.arange(len(order))
    width = .8 / 4
    offsets = [(i - 1.5) * width for i in range(4)]
    # Palettes sampled at the same five equally spaced perceptual lightness levels.
    import matplotlib
    from matplotlib.colors import to_hex
    def lightness(color):
        y = C._luminance(color)
        return 116 * y ** (1 / 3) - 16 if y > (6 / 29) ** 3 else (29 / 3) ** 3 * y
    target_lightness = [80., 65., 50., 35., 20.]  # steps 1..5, top to bottom
    palettes = {}
    for name in ['plasma']:
        candidates = [to_hex(matplotlib.colormaps[name](t)) for t in np.linspace(0, 1, 256)]
        palettes[name] = [min(candidates, key=lambda c: abs(lightness(c) - target))
                          for target in target_lightness]
    other_color = palettes['plasma'][4]
    # Steps 1/2: shared; 3/4: global; 5: other; all from the same plasma ramp.
    # Other work forms the darkest base; writes sit above reads in each pair.
    stack = [
        ('other', other_color, '', 'L1 – other'),
        ('global_reads', palettes['plasma'][3], '', 'L1 – global read'),
        ('global_writes', palettes['plasma'][2], '', 'L1 – global write'),
        ('shared_reads', palettes['plasma'][1], '', 'L1 – shared read'),
        ('shared_writes', palettes['plasma'][0], '', 'L1 – shared write'),
    ]
    measured_lightness = [lightness(entry[1]) for entry in reversed(stack)]
    assert all(abs(actual - target) < .4 for actual, target in zip(measured_lightness, target_lightness))
    assert all(abs(a - b - 15) < .6 for a, b in zip(measured_lightness, measured_lightness[1:]))
    bottom = np.zeros(len(order))
    for key, color, hatch, label in stack:
        values = np.array([rows[c]['peak_points'][key] for c in order])
        ax.bar(x + offsets[0], values, width, bottom=bottom, color=color,
               edgecolor=C.INK if hatch else 'white', linewidth=.2 if hatch else .3,
               hatch=hatch, label=label)
        bottom += values
    for i, value in enumerate(bottom):
        ax.text(i + offsets[0], value + 1.5, f'{value:.0f}', ha='center', va='bottom',
                fontsize=C.FS['annot'])
    # Neutral versions of the same plasma steps: approximately L* 80, 65, 50.
    context_colors = {name: C.desaturate(color)
                      for name, color in zip(['l2', 'dram', 'compute'], palettes['plasma'][:3])}
    ax.bar(x + offsets[1], [metrics[c]['l2_pct'] for c in order], width,
           color=context_colors['l2'], edgecolor=C.INK,
           linewidth=0, hatch='////', label='L2')
    ax.bar(x + offsets[2], [metrics[c]['dram_pct'] for c in order], width,
           color=context_colors['dram'], edgecolor=C.INK,
           linewidth=0, hatch='....', rasterized=True, label='Device memory')
    for i, chip in enumerate(order):
        value = metrics[chip]['dram_pct']
        ax.text(i + offsets[2], value + 1.5, f'{value:.0f}', ha='center', va='bottom',
                fontsize=C.FS['annot'])
    ax.bar(x + offsets[3], [metrics[c]['compute_pct'] for c in order], width,
           color=context_colors['compute'], edgecolor=C.INK, linewidth=0, hatch='++++', label='SM (compute)')
    labels = {'b300':'B300', 'h100':'H100', 'a100':'A100', 'rtxpro':'RTX PRO', 'l40s':'L40S'}
    ax.set_xticks(x)
    ax.set_xticklabels([labels[c] for c in order])
    ax.tick_params(axis='x', length=0, pad=1)
    ax.set_ylabel("throughput (% of peak)")
    ax.set_ylim(0, 100)
    fig.tight_layout(pad=.3)
    handles, names = ax.get_legend_handles_labels()
    # Four rows, eight entries: shared pair then global pair in left column;
    # other and the three unstacked units in right column.
    legend_order = [4, 3, 2, 1, 0, 5, 6, 7]
    legend = C.legend_below(fig, handles=[handles[i] for i in legend_order],
                            labels=[names[i] for i in legend_order], ncol=2,
                            columnspacing=.9, handlelength=1.5, handleheight=.9, handletextpad=.3,
                            labelspacing=.3, borderpad=.2)
    C.rasterize_dotted_legend(legend)
    C.save(fig, 'fig_pipes', width='column')
    # Keep printed fonts at the theme size while checking the complete legend.
    fig.canvas.draw()
    renderer=fig.canvas.get_renderer()
    boxes=[text.get_window_extent(renderer) for text in legend.get_texts()]
    assert all(not a.overlaps(b) for i,a in enumerate(boxes) for b in boxes[i+1:]), 'legend text overlaps'
    provenance = {
        'theme_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'renderer_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'inputs':{n:hashlib.sha256((here/n).read_bytes()).hexdigest() for n in ['accepted.json','directions.json','evidence.tar.gz']},
        'order':order, 'stack_bottom_to_top':[s[0] for s in stack],
        'legend_labels':{s[0]:s[3] for s in stack},
        'style':{'font_sizes_pt':C.FS, 'font_family':'DejaVu Sans',
                 'other_palette':'plasma','other_fill':other_color,'other_hatch':'','l2_hatch':'////',
                 'global_palette':'plasma','shared_palette':'plasma',
                 'context_colors':context_colors,
                 'context_palette_source':'luminance-preserving grayscale of plasma steps 1–3',
                 'context_lightness':{k:lightness(v) for k,v in context_colors.items()},
                 'context_hatches':{'l2':'////','dram':'....','compute':'++++'},
                 'context_border_width':0,
                 'legend_handlelength':1.5,'legend_handleheight':.9,
                 'stack_colors':{s[0]:s[1] for s in stack},
                 'lightness_space':'CIELAB L* from sRGB relative luminance',
                 'target_lightness_top_to_bottom':target_lightness,
                 'measured_lightness_top_to_bottom':measured_lightness,
                 'five_step_palettes':palettes,
                 'hatch_linewidth':plt.rcParams['hatch.linewidth'],
                 'print_width':'column'},
        'rows':{c:{'kernel':rows[c]['kernel'],'global_direction_method':rows[c]['direction_method'],
                   'l1_segments_peak_points':rows[c]['peak_points'],
                   'l2_pct':metrics[c]['l2_pct'],'dram_pct':metrics[c]['dram_pct'],
                   'compute_pct':metrics[c]['compute_pct']} for c in order},
        'paper_text_changed':False,
        'note':'See experiments/pipes/README.md for A100/L40S estimates and capture acceptance.'
    }
    for ext in ['pdf','png']:
        provenance['output_'+ext+'_sha256']=hashlib.sha256((C.OUTDIR/('fig_pipes.'+ext)).read_bytes()).hexdigest()
    print('Stack lightness, top to bottom:', [round(v, 2) for v in measured_lightness])
    (C.OUTDIR/'fig_pipes-provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')

if __name__ == '__main__':
    main()
