from typing import Tuple

from pyproj import Transformer


class Converter:
    def __init__(self, origin_projection: str, target_projection: str):
        self.transformer = Transformer.from_crs(origin_projection, target_projection)

    def convert(self, point: Tuple[float, float]):
        return self.transformer.transform(*point)
