import ctypes

lib = ctypes.CDLL('./libmath.so')

lib.add.argtypes = [ctypes.c_int32, ctypes.c_int32]
lib.add.restype = ctypes.c_int32

lib.multiply.argtypes = [ctypes.c_double, ctypes.c_double]
lib.multiply.restype = ctypes.c_double

print(lib.add(10, 20))
print(lib.multiply(1.5, 2))


class Point(ctypes.Structure):
        _fields_ = [
                ('x', ctypes.c_int),
                ('y', ctypes.c_int),
        ]


lib.move_point.argtypes = [
        ctypes.POINTER(Point),
        ctypes.c_int,
        ctypes.c_int,
]
lib.move_point.restype = None

p = Point(10, 20)

lib.move_point(ctypes.byref(p), 5, 10)
