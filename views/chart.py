"""Map → Chart: the sector map, as a picture."""

import os

ID, LABEL = "chart", "Chart"

CSS = """
  /* The one panel that takes the window rather than the 60rem column. */
  .wrap.chart { max-width: none; }
  .chartimg { display: block; margin-top: .75rem; }
  .chartimg img { width: 100%; height: auto; border: 1px solid var(--line);
                  border-radius: 6px; }
"""

JS = r"""
VIEW.chart = {
  bare: true,
  sub: 'the Sirius sector and every jump between its systems',
  // Drawn once. The poll calls render() every five seconds, and rewriting this
  // would throw away a decoded 2560px image and decode it again, forever.
  draw: () => $('#list .chartimg, #list .nochart') ? null :
    '<p class="note">Click it for the full image in its own tab.</p>' +
    '<a class="chartimg" href="map.jpg" target="_blank" rel="noopener">' +
    '<img src="map.jpg" alt="Freelancer system chart"' +
    ' onerror="this.closest(\'.chartimg\').outerHTML = NOCHART"></a>',
};

// No chart ships with this repo: the good ones are fan-made and not ours to
// redistribute. Drop any sector map in beside serve.py under this name.
const NOCHART =
  '<p class="note nochart">No chart here. Save any Freelancer sector map as ' +
  '<code>freelancer-map.jpg</code> beside <code>serve.py</code> and reload. ' +
  'The community ones are easy to find and far better than anything ' +
  'generated from the game files.</p>';
"""

FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "freelancer-map.jpg")
