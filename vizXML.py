from __future__ import annotations

import math
import xml.etree.ElementTree as ET
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from graphviz import Digraph


class VizXML:
    """Turn an XML document into a weighted, hierarchical Graphviz diagram."""

    def __init__(
        self,
        xml_file: str | Path,
        dia_name: str = "XML_Diagram",
        *,
        font_name: str = "Gill Sans",
        font_size: int = 10,
        show_attribute_values: bool = True,
        max_attribute_values: int = 2,
        show_edge_weights: bool = True,
    ) -> None:
        self.xml_file = Path(xml_file)
        self.dia_name = dia_name
        self.font_name = font_name
        self.font_size = str(font_size)
        self.show_attribute_values = show_attribute_values
        self.max_attribute_values = max_attribute_values
        self.show_edge_weights = show_edge_weights

        self.root: Optional[ET.Element] = None
        self.edges: list[dict] = []
        self.nodes: list[str] = []
        self.node_data: dict[str, dict] = {}
        self.dot: Optional[Digraph] = None

        self.parse_xml()
        self.run()

    # ---------- XML helpers ----------

    @staticmethod
    def local_name(tag: str) -> str:
        """Remove ElementTree's {namespace} prefix for readable labels."""
        return tag.rsplit("}", 1)[-1] if tag.startswith("{") else tag

    @classmethod
    def child_path(cls, parent_path: str, tag: str) -> str:
        return f"{parent_path}/{cls.local_name(tag)}"

    def parse_xml(self) -> None:
        try:
            self.root = ET.parse(self.xml_file).getroot()
        except (ET.ParseError, OSError) as exc:
            raise ValueError(f"Could not read XML file {self.xml_file!s}: {exc}") from exc

    # ---------- Traverse and collect structure ----------

    def walk(self, element: ET.Element, path: str = "") -> None:
        """Collect full structural paths, edge frequencies and node metadata."""
        assert self.root is not None

        current_path = self.child_path(path, element.tag)
        meta = self.node_data.setdefault(
            current_path,
            {"tag": self.local_name(element.tag),
             "attributes": defaultdict(set),
             "text_values": set(),
             "depth": current_path.count("/") - 1},
        )

        for key, value in element.attrib.items():
            meta["attributes"][self.local_name(key)].add(str(value))

        text_value = (element.text or "").strip()
        if text_value:
            meta["text_values"].add(text_value)

        for child in element:
            child_path = self.child_path(current_path, child.tag)
            self.edge_counter[(current_path, child_path)] += 1
            self.walk(child, current_path)

    def aggregate_edges(self) -> None:
        self.edges = [
            {"src": src, "dst": dst, "wgt": weight}
            for (src, dst), weight in sorted(self.edge_counter.items())
        ]
        self.nodes = sorted(self.node_data, key=lambda p: (p.count("/"), p))

    # ---------- Visual styling ----------

    @staticmethod
    def scale(weight: int, maximum: int) -> float:
        if maximum <= 1:
            return 0.0
        return math.log1p(weight) / math.log1p(maximum)

    def edge_color(self, weight: int, maximum: int) -> str:
        # Graphviz HSV string: hue, saturation, value.
        strength = self.scale(weight, maximum)
        saturation = 0.48 + 0.42 * strength
        value = 0.88 - 0.18 * strength
        return f"0.57 {saturation:.3f} {value:.3f}"

    @staticmethod
    def _short_values(values: set[str], limit: int) -> str:
        ordered = sorted(values)
        if len(ordered) <= limit:
            return ", ".join(ordered)
        shown = ", ".join(ordered[:limit])
        return f"{shown}, … (+{len(ordered) - limit})"

    def node_label(self, path: str) -> str:
        meta = self.node_data[path]
        lines = [meta["tag"]]

        for attr_name, values in sorted(meta["attributes"].items()):
            if self.show_attribute_values:
                value_text = self._short_values(values, self.max_attribute_values)
                lines.append(f"@{attr_name}: {value_text}")
            else:
                lines.append(f"@{attr_name}")

        return "\n".join(lines)

    def create_graph(self) -> None:
        self.dot = Digraph(name="XML", comment=self.dia_name, format="svg")
        self.dot.attr(
            "graph",
            rankdir="TB",
            bgcolor="white",
            pad="0.28",
            nodesep="0.34",
            ranksep="0.58",
            splines="spline",
            overlap="false",
            fontname=self.font_name,
            fontsize="12",
            labelloc="t",
            label=self.dia_name.replace("_", " "),
            fontcolor="#263445",
        )
        self.dot.attr(
            "node",
            shape="box",
            style="rounded,filled",
            fillcolor="#F1F6FB",
            color="#8AA2B8",
            penwidth="1.15",
            fontname=self.font_name,
            fontsize=self.font_size,
            fontcolor="#203040",
            margin="0.16,0.10",
        )
        self.dot.attr(
            "edge",
            fontname=self.font_name,
            fontsize="8",
            fontcolor="#536579",
            arrowsize="0.72",
            arrowhead="vee",
        )

        # Root and leaf nodes get subtle visual distinctions.
        for path in self.nodes:
            meta = self.node_data[path]
            is_root = meta["depth"] == 0
            is_leaf = not any(edge["src"] == path for edge in self.edges)

            if is_root:
                attrs = {
                    "shape": "box",
                    "style": "rounded,filled,bold",
                    "fillcolor": "#DCEBFA",
                    "color": "#4779A8",
                    "penwidth": "1.7",
                }
            elif is_leaf:
                attrs = {
                    "shape": "box",
                    "style": "rounded,filled",
                    "fillcolor": "#F5F7F9",
                    "color": "#B3C0CC",
                }
            else:
                attrs = {}

            self.dot.node(
                path,
                label=self.node_label(path),
                tooltip=path,
                **attrs,
            )

        max_weight = max((edge["wgt"] for edge in self.edges), default=1)
        for edge in self.edges:
            weight = edge["wgt"]
            attrs = {
                "color": self.edge_color(weight, max_weight),
                "penwidth": f"{0.9 + 2.0 * self.scale(weight, max_weight):.2f}",
            }
            if self.show_edge_weights and weight > 1:
                attrs["label"] = f"×{weight}"
            self.dot.edge(edge["src"], edge["dst"], **attrs)

    # ---------- Public pipeline / output ----------

    def run(self) -> None:
        if self.root is None:
            raise RuntimeError("XML has not been loaded.")

        self.edge_counter: Counter = Counter()
        self.node_data = {}
        self.walk(self.root)
        self.aggregate_edges()
        self.create_graph()

    def render(
        self,
        output_format: str = "svg",
        *,
        view: bool = False,
        cleanup: bool = True,
    ) -> str:
        if self.dot is None:
            raise RuntimeError("Graph has not been built.")
        return self.dot.render(
            filename=self.dia_name,
            format=output_format,
            view=view,
            cleanup=cleanup,
        )

    @property
    def source(self) -> str:
        if self.dot is None:
            raise RuntimeError("Graph has not been built.")
        return self.dot.source



# Initialize visualizer
viz = VizXML(
    xml_file="sample.xml",
    dia_name="Company_XML",
    font_name="DejaVu Sans",
    font_size=10,
    show_attribute_values=True,
    max_attribute_values=2,
    show_edge_weights=True
)

# Generate SVG diagram
viz.render(
    output_format="svg",
    view=True
)

# Display node and edge information
print("\nNODES:")
print(viz.nodes)

print("\nEDGES:")
for edge in viz.edges:
    print(edge)

