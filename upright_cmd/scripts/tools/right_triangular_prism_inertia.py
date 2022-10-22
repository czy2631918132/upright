#!/usr/bin/env python3
"""This script computes the inertia tensor for right triangular prisms."""
import sympy
import numpy as np
import IPython


def skew(v):
    return sympy.Matrix([[0, -v[2], v[1]], [v[2], 0, -v[0]], [-v[1], v[0], 0]])

r = sympy.symbols("x,y,z")
x, y, z = r
h = sympy.symbols("hx,hy,hz")  # half extents
a = [2 * h[0] / 3, 2 * h[1] / 3, 2 * h[2] / 3]

R = skew(r)
A = -R @ R

# fmt: off
J = A.integrate(
        (r[0], -a[0], a[0] * (1 - z/a[2]))
    ).integrate(
        (r[1], -h[1], h[1])
    ).integrate(
        (r[2], -a[2], 2 * a[2])
    )
# fmt: on

J.simplify()
print(J)
# P, D = J.diagonalize()

# convert to numpy array with particular values
Jr = J.subs({h[0] : 0.5, h[1]: 0.5, h[2]: 0.5})
Jr = np.array(Jr).astype(np.float64)

IPython.embed()
