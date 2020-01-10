import sys
sys.path.append(r"C:\Users\Public\pype_env2\Lib\site-packages")
from PIL import Image, ImageFont, ImageDraw, ImageEnhance, ImageColor
from uuid import uuid4

class BaseObj:
    """Base Object for slates."""

    obj_type = None
    available_parents = []

    def __init__(self, parent, style={}, name=None):
        if not self.obj_type:
            raise NotImplemented(
                "Class don't have set object type <{}>".format(
                    self.__class__.__name__
                )
            )

        parent_obj_type = None
        if parent:
            parent_obj_type = parent.obj_type

        if parent_obj_type not in self.available_parents:
            expected_parents = ", ".join(self.available_parents)
            raise Exception((
                "Invalid parent <{}> for <{}>. Expected <{}>"
            ).format(
                parent.__class__.__name__, self.obj_type, expected_parents
            ))

        self.parent = parent
        self._style = style

        self.id = uuid4()
        self.parent = parent
        self.name = name
        self._style = style
        self.items = {}
        self.final_style = None

    @property
    def main_style(self):
        default_style_v1 = {
            "*": {
                "font-family": "arial",
                "font-size": 26,
                "font-color": "#ffffff",
                "font-bold": False,
                "font-italic": False,
                "bg-color": None,
                "bg-alter-color": None,
                "alignment-vertical": "left", #left, center, right
                "alignment-horizontal": "top", #top, center, bottom
                "padding": 0,
                # "padding-left": 0,
                # "padding-right": 0,
                # "padding-top": 0,
                # "padding-bottom": 0
                "margin": 0,
                # "margin-left": 0,
                # "margin-right": 0,
                # "margin-top": 0,
                # "margin-bottom": 0
            },
            "layer": {},
            "image": {},
            "text": {},
            "table": {},
            "table-item": {},
            "table-item-col-0": {},
            "#MyName": {}
        }
        return default_style_v1

    @property
    def is_drawing(self):
        return self.parent.is_drawing

    @property
    def height(self):
        raise NotImplementedError(
            "Attribute `height` is not implemented for <{}>".format(
                self.__clas__.__name__
            )
        )

    @property
    def width(self):
        raise NotImplementedError(
            "Attribute `width` is not implemented for <{}>".format(
                self.__clas__.__name__
            )
        )

    @property
    def full_style(self):
        if self.is_drawing and self.final_style is not None:
            return self.final_style

        if self.parent is not None:
            style = dict(val for val in self.parent.full_style.items())
        else:
            style = self.main_style

        for key, value in self._style.items():
            if key in style:
                style[key] = value
            style.update()

        if self.is_drawing:
            self.final_style = style

        return style

    @property
    def style(self):
        style = self.full_style
        style.update(self._style)

        base = style.get("*", style.get("global")) or {}
        obj_specific = style.get(self.obj_type) or {}
        name_specific = {}
        if self.name:
            name = str(self.name)
            if not name.startswith("#"):
                name += "#"
            name_specific = style.get(name) or {}

        output = {}
        output.update(base)
        output.update(obj_specific)
        output.update(name_specific)

        return output

    @property
    def pos_x(self):
        return 0

    @property
    def pos_y(self):
        return 0

    @property
    def pos_start(self):
        return (self.pos_x, self.pos_y)

    @property
    def pos_end(self):
        pos_x, pos_y = self.pos_start
        pos_x += self.width
        pos_y += self.height
        return (pos_x, pos_y)

    @property
    def max_width(self):
        return self.style.get("max-width") or (self.width * 1)

    @property
    def max_height(self):
        return self.style.get("max-height") or (self.height * 1)

    @property
    def max_content_width(self):
        width = self.max_width
        padding = self.style["padding"]
        padding_left = self.style.get("padding-left") or padding
        padding_right = self.style.get("padding-right") or padding
        return (width - (padding_left + padding_right))

    @property
    def max_content_height(self):
        height = self.max_height
        padding = self.style["padding"]
        padding_top = self.style.get("padding-top") or padding
        padding_bottom = self.style.get("padding-bottom") or padding
        return (height - (padding_top + padding_bottom))

    def add_item(self, item):
        self.items[item.id] = item

    def reset(self):
        self.final_style = None
        for item in self.items.values():
            item.reset()


class MainFrame(BaseObj):

    obj_type = "main_frame"
    available_parents = [None]

    def __init__(self, width, height, style={}, parent=None, name=None):
        super(MainFrame, self).__init__(parent, style, name)
        self._width = width
        self._height = height
        self._is_drawing = False

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    @property
    def is_drawing(self):
        return self._is_drawing

    def draw(self, path):
        self._is_drawing = True
        bg_color = self.style["bg-color"]
        image = Image.new("RGB", (self.width, self.height))#, color=bg_color)
        for item in self.items.values():
            item.draw(image)

        image.save(path)
        self._is_drawing = False
        self.reset()



class Layer(BaseObj):
    obj_type = "layer"
    available_parents = ["main_frame", "layer"]

    # Direction can be 0=horizontal/ 1=vertical
    def __init__(self, *args, **kwargs):
        super(Layer, self).__init__(*args, **kwargs)

    @property
    def pos_x(self):
        if self.parent.obj_type == self.obj_type:
            pos_x = self.parent.item_pos_x(self.id)
        else:
            pos_x = self.parent.pos_x
        return pos_x

    @property
    def pos_y(self):
        if self.parent.obj_type == self.obj_type:
            pos_y = self.parent.item_pos_y(self.id)
        else:
            pos_y = self.parent.pos_y
        return pos_y

    @property
    def direction(self):
        direction = self.style.get("direction", 0)
        if direction not in (0, 1):
            raise Exception(
                "Direction must be 0 or 1 (0 is Vertical / 1 is horizontal)!"
            )
        return direction

    def item_pos_x(self, item_id):
        pos_x = self.pos_x
        if self.direction != 0:
            for id, item in self.items.items():
                if id == item_id:
                    break
                pos_x += item.width
                if item.obj_type != "image":
                    pos_x += 1

        if pos_x != self.pos_x:
            pos_x += 1
        return pos_x

    def item_pos_y(self, item_id):
        pos_y = self.pos_y
        if self.direction != 1:
            for id, item in self.items.items():
                if item_id == id:
                    break
                pos_y += item.height
                if item.obj_type != "image":
                    pos_y += 1

        return pos_y

    @property
    def height(self):
        height = 0
        for item in self.items.values():
            if self.direction == 0:
                if height > item.height:
                    continue

                # times 1 because won't get object pointer but number
                height = item.height * 1
            else:
                height += item.height

        min_height = self.style.get("min-height")
        if min_height > height:
            return min_height
        return height

    @property
    def width(self):
        width = 0
        for item in self.items.values():
            if self.direction == 0:
                if width > item.width:
                    continue

                # times 1 because won't get object pointer but number
                width = item.width * 1
            else:
                width += item.width

        min_width = self.style.get("min-width")
        if min_width > width:
            return min_width
        return width

    def draw(self, image, drawer=None):
        if drawer is None:
            drawer = ImageDraw.Draw(image)

        for item in self.items.values():
            item.draw(image, drawer)


class BaseItem(BaseObj):
    available_parents = ["layer"]

    def __init__(self, *args, **kwargs):
        super(BaseItem, self).__init__(*args, **kwargs)

    @property
    def pos_x(self):
        return self.parent.item_pos_x(self.id)

    @property
    def pos_y(self):
        return self.parent.item_pos_y(self.id)

    @property
    def content_pos_x(self):
        padding = self.style["padding"]
        padding_left = self.style.get("padding-left") or padding

        margin = self.style["margin"]
        margin_left = self.style.get("margin-left") or margin

        return self.pos_x + margin_left + padding_left

    @property
    def content_pos_y(self):
        padding = self.style["padding"]
        padding_top = self.style.get("padding-top") or padding

        margin = self.style["margin"]
        margin_top = self.style.get("margin-top") or margin

        return self.pos_y + margin_top + padding_top

    @property
    def content_width(self):
        raise NotImplementedError(
            "Attribute <content_width> is not implemented"
        )

    @property
    def content_height(self):
        raise NotImplementedError(
            "Attribute <content_height> is not implemented"
        )

    @property
    def width(self):
        width = self.content_width

        padding = self.style["padding"]
        padding_left = self.style.get("padding-left") or padding
        padding_right = self.style.get("padding-right") or padding

        margin = self.style["margin"]
        margin_left = self.style.get("margin-left") or margin
        margin_right = self.style.get("margin-right") or margin

        return (
            width +
            margin_left + margin_right +
            padding_left + padding_right
        )

    @property
    def height(self):
        height = self.content_height

        padding = self.style["padding"]
        padding_top = self.style.get("padding-top") or padding
        padding_bottom = self.style.get("padding-bottom") or padding

        margin = self.style["margin"]
        margin_top = self.style.get("margin-top") or margin
        margin_bottom = self.style.get("margin-bottom") or margin

        return (
            height +
            margin_bottom + margin_top +
            padding_top + padding_bottom
        )

    def add_item(self, *args, **kwargs):
        raise Exception("Can't add item to an item, use layers instead.")

    def draw(self, image, drawer):
        raise NotImplementedError(
            "Method `draw` is not implemented for <{}>".format(
                self.__clas__.__name__
            )
        )

class ItemImage(BaseItem):
    obj_type = "image"

    def __init__(self, image_path, *args, **kwargs):
        super(ItemImage, self).__init__(*args, **kwargs)
        self.image_path = image_path

    def draw(self, image, drawer):
        paste_image = Image.open(self.image_path)
        paste_image = paste_image.resize(
            (self.content_width, self.content_height),
            Image.ANTIALIAS
        )
        image.paste(
            paste_image,
            (self.content_pos_x, self.content_pos_y)
        )

    @property
    def content_width(self):
        return self.style.get("width")

    @property
    def content_height(self):
        return self.style.get("height")


class ItemText(BaseItem):
    obj_type = "text"

    def __init__(self, value, *args, **kwargs):
        super(ItemText, self).__init__(*args, **kwargs)
        self.value = value

    def draw(self, image, drawer):
        bg_color = self.style["bg-color"]
        if bg_color and bg_color.lower() != "transparent":
            padding = self.style["padding"]

            padding_left = self.style.get("padding-left") or padding
            padding_right = self.style.get("padding-right") or padding
            padding_top = self.style.get("padding-top") or padding
            padding_bottom = self.style.get("padding-bottom") or padding
            # TODO border outline styles
            drawer.rectangle(
                (self.pos_start, self.pos_end),
                fill=bg_color,
                outline=None
            )

        text_pos_start = (self.content_pos_x, self.content_pos_y)

        font_color = self.style["font-color"]
        font_family = self.style["font-family"]
        font_size = self.style["font-size"]

        font = ImageFont.truetype(font_family, font_size)
        drawer.text(
            text_pos_start,
            self.value,
            font=font,
            fill=font_color
        )

    @property
    def content_width(self):
        font_family = self.style["font-family"]
        font_size = self.style["font-size"]

        font = ImageFont.truetype(font_family, font_size)
        width = font.getsize(self.value)[0]
        return width

    @property
    def content_height(self):
        font_family = self.style["font-family"]
        font_size = self.style["font-size"]

        font = ImageFont.truetype(font_family, font_size)
        height = font.getsize(self.value)[1]
        return height


class ItemTable(BaseItem):

    obj_type = "table"

    def __init__(self, values, *args, **kwargs):
        super(ItemTable, self).__init__(*args, **kwargs)
        self.size_values = None
        self.values_by_cords = None

        self.prepare_values(values)
        self.calculate_sizes()

    def prepare_values(self, _values):
        values = []
        values_by_cords = []
        for row_idx, row in enumerate(_values):
            if len(values_by_cords) < row_idx + 1:
                for i in range(len(values_by_cords), row_idx + 1):
                    values_by_cords.append([])

            for col_idx, col in enumerate(_values[row_idx]):
                if len(values_by_cords[row_idx]) < col_idx + 1:
                    for i in range(len(values_by_cords[row_idx]), col_idx + 1):
                        values_by_cords[row_idx].append("")

                if not col:
                    col = ""
                col_item = TableField(row_idx, col_idx, col, self)
                values_by_cords[row_idx][col_idx] = col_item
                values.append(col_item)

        self.values = values
        self.values_by_cords = values_by_cords

    def calculate_sizes(self):
        row_heights = []
        col_widths = []
        for row_idx, row in enumerate(self.values_by_cords):
            row_heights.append(0)
            for col_idx, col_item in enumerate(row):
                if len(col_widths) < col_idx + 1:
                    col_widths.append(0)

                _width = col_widths[col_idx]
                item_width = col_item.width
                if _width < item_width:
                    col_widths[col_idx] = item_width

                _height = row_heights[row_idx]
                item_height = col_item.height
                if _height < item_height:
                    row_heights[row_idx] = item_height

        self.size_values = (row_heights, col_widths)

    def draw(self, image, drawer):
        bg_color = self.style["bg-color"]
        if bg_color and bg_color.lower() != "transparent":
            padding = self.style["padding"]

            padding_left = self.style.get("padding-left") or padding
            padding_right = self.style.get("padding-right") or padding
            padding_top = self.style.get("padding-top") or padding
            padding_bottom = self.style.get("padding-bottom") or padding
            # TODO border outline styles
            drawer.rectangle(
                (self.pos_start, self.pos_end),
                fill=bg_color,
                outline=None
            )

        for value in self.values:
            value.draw(image, drawer)

    @property
    def content_width(self):
        row_heights, col_widths = self.size_values
        width = 0
        for _width in col_widths:
            width += _width

        if width != 0:
            width -= 1
        return width

    @property
    def content_height(self):
        row_heights, col_widths = self.size_values
        height = 0
        for _height in row_heights:
            height += _height

        if height != 0:
            height -= 1
        return height

    def pos_info_by_cord(self, cord_x, cord_y):
        row_heights, col_widths = self.size_values
        pos_x = self.pos_x
        pos_y = self.pos_y
        width = 0
        height = 0
        for idx, value in enumerate(col_widths):
            if cord_y == idx:
                width = value
                break
            pos_x += value

        for idx, value in enumerate(row_heights):
            if cord_x == idx:
                height = value
                break
            pos_y += value

        padding = self.style["padding"]

        padding_left = self.style.get("padding-left") or padding
        padding_top = self.style.get("padding-top") or padding
        pos_x += padding_left
        pos_y += padding_top
        return (pos_x, pos_y, width, height)

    def filled_style(self, cord_x, cord_y):
        # TODO CHANGE STYLE BY CORDS
        return self.style


class TableField(BaseItem):

    obj_type = "table-item"
    available_parents = ["table"]

    def __init__(self, cord_x, cord_y, value, *args, **kwargs):
        super(TableField, self).__init__(*args, **kwargs)
        self.cord_x = cord_x
        self.cord_y = cord_y
        self.value = value

    @property
    def content_width(self):
        font_family = self.style["font-family"]
        font_size = self.style["font-size"]

        font = ImageFont.truetype(font_family, font_size)
        width = font.getsize(self.value)[0] + 1
        return width

    @property
    def content_height(self):
        font_family = self.style["font-family"]
        font_size = self.style["font-size"]

        font = ImageFont.truetype(font_family, font_size)
        height = font.getsize(self.value)[1] + 1
        return height

    def content_pos_x(self, pos_x, width):
        padding = self.style["padding"]
        padding_left = self.style.get("padding-left") or padding
        return pos_x + padding_left

    def content_pos_y(self, pos_y, height):
        padding = self.style["padding"]
        padding_top = self.style.get("padding-top") or padding
        return pos_y + padding_top

    def draw(self, image, drawer):
        pos_x, pos_y, width, height = (
            self.parent.pos_info_by_cord(self.cord_x, self.cord_y)
        )
        pos_start = (pos_x, pos_y)
        pos_end = (pos_x + width, pos_y + height)
        bg_color = self.style["bg-color"]
        if bg_color and bg_color.lower() != "transparent":
            padding = self.style["padding"]

            padding_left = self.style.get("padding-left") or padding
            padding_right = self.style.get("padding-right") or padding
            padding_top = self.style.get("padding-top") or padding
            padding_bottom = self.style.get("padding-bottom") or padding
            # TODO border outline styles
            drawer.rectangle(
                (pos_start, pos_end),
                fill=bg_color,
                outline=None
            )

        text_pos_start = (
            self.content_pos_x(pos_x, width),
            self.content_pos_y(pos_y, height)
        )

        font_color = self.style["font-color"]
        font_family = self.style["font-family"]
        font_size = self.style["font-size"]

        font = ImageFont.truetype(font_family, font_size)
        drawer.text(
            text_pos_start,
            self.value,
            font=font,
            fill=font_color
        )

if __name__ == "__main__":
    main_style = {
        "bg-color": "#777777"
    }
    text_1_style = {
        "padding": 10,
        "bg-color": "#00ff77"
    }
    text_2_style = {
        "padding": 8,
        "bg-color": "#ff0066"
    }
    text_3_style = {
        "padding": 0,
        "bg-color": "#ff5500"
    }
    main = MainFrame(1920, 1080, style=main_style)
    layer = Layer(parent=main)
    main.add_item(layer)

    text_1 = ItemText("Testing message 1", layer, text_1_style)
    text_2 = ItemText("Testing message 2", layer, text_2_style)
    text_3 = ItemText("Testing message 3", layer, text_3_style)
    table_1_items = [["0", "Output text 1"], ["1", "Output text 2"], ["2", "Output text 3"]]
    table_1_style = {
        "padding": 8,
        "bg-color": "#0077ff"
    }
    table_1 = ItemTable(table_1_items, layer, table_1_style)

    image_1_style = {
        "width": 240,
        "height": 120,
        "bg-color": "#7733aa"
    }
    image_1_path = r"C:\Users\jakub.trllo\Desktop\Tests\files\image\kitten.jpg"
    image_1 = ItemImage(image_1_path, layer, image_1_style)

    layer.add_item(text_1)
    layer.add_item(text_2)
    layer.add_item(table_1)
    layer.add_item(image_1)
    layer.add_item(text_3)
    dst = r"C:\Users\jakub.trllo\Desktop\Tests\files\image\test_output2.png"
    main.draw(dst)

    print("*** Drawing done :)")


style_schema = {
    "alignment": {
        "description": "Alignment of item",
        "type": "string",
        "enum": ["left", "right", "center"],
        "example": "left"
    },
    "font-family": {
        "description": "Font type",
        "type": "string",
        "example": "Arial"
    },
    "font-size": {
        "description": "Font size",
        "type": "integer",
        "example": 26
    },
    "font-color": {
        "description": "Font color",
        "type": "string",
        "regex": (
            "^[#]{1}[a-fA-F0-9]{1}$"
            " | ^[#]{1}[a-fA-F0-9]{3}$"
            " | ^[#]{1}[a-fA-F0-9]{6}$"
        ),
        "example": "#ffffff"
    },
    "font-bold": {
        "description": "Font boldness",
        "type": "boolean",
        "example": True
    },
    "bg-color": {
        "description": "Background color, None means transparent",
        "type": ["string", None],
        "regex": (
            "^[#]{1}[a-fA-F0-9]{1}$"
            " | ^[#]{1}[a-fA-F0-9]{3}$"
            " | ^[#]{1}[a-fA-F0-9]{6}$"
        ),
        "example": "#333"
    },
    "bg-alter-color": None,
}