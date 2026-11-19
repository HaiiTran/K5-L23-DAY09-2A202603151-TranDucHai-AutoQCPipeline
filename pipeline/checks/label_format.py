"""CHECK 2 — Dòng nhãn YOLO: sai định dạng, ID lớp lạ, box tràn ảnh, box rỗng, box lặp.   (Script 2 trong slide)   ★★

Test:  pytest tests/test_label_format.py -q

Mỗi dòng nhãn: `id cx cy w h` (5 số, toạ độ 0–1). Trả về list[Issue]; `Issue.line` = số dòng (đếm từ 1).

| code             | severity | khi nào                                                                  |
|------------------|----------|--------------------------------------------------------------------------|
| BAD_FORMAT       | ERROR    | không đúng 5 cột số (dùng `parse_yolo_line`, bắt `ValueError`)           |
| BAD_CLASS_ID     | ERROR    | id lớp ngoài 0..len(ds.classes)-1                                        |
| BOX_ZERO         | ERROR    | w <= 0 hoặc h <= 0                                                       |
| BOX_OUT_OF_IMAGE | ERROR    | mép box vượt [0,1] quá `cfg["label_format"]["overflow_tol"]`; extra={"overflow": mức tràn} |
| DUP_BOX          | ERROR    | cùng lớp với một dòng TRƯỚC ĐÓ và IoU > `dup_box_iou`; báo ở dòng SAU    |
| BOX_TINY         | WARN     | cạnh ngắn của box (px) < `min_box_px`  (cần `ds.image_size(stem)`)       |
| BOX_HUGE         | WARN     | w*h > `max_box_frac`                                                     |

Gợi ý
- Mép trái = x - w/2, mép phải = x + w/2 (xem câu hỏi "dòng YOLO nào lỗi?" trong slide).
- Một dòng hỏng (BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO) thì `continue`, đừng kiểm tiếp hình học của dòng đó.
- Dòng thiếu cột làm script của slide dừng giữa chừng: đây là lý do phải `try/except`.
- `iou_xywh(a, b)` có sẵn trong common.py.
- Ngưỡng nằm trong `cfg["label_format"]` — đừng viết cứng số vào code.
"""
from ..common import ERROR, WARN, Issue, iou_xywh, parse_yolo_line  # noqa: F401


def run(ds, cfg):
    settings = cfg["label_format"]
    issues = []

    for label_file in ds.label_files():
        stem = label_file.stem
        size = ds.image_size(stem)
        width, height = size if size is not None else (None, None)
        previous = []

        for line_number, text in ds.read_label_lines(stem) or []:
            try:
                class_id, cx, cy, box_width, box_height = parse_yolo_line(text)
            except ValueError as exc:
                issues.append(Issue("label_format", ERROR, "BAD_FORMAT", stem,
                                    f"dòng nhãn không hợp lệ: {exc}", line_number))
                continue

            if not 0 <= class_id < len(ds.classes):
                issues.append(Issue("label_format", ERROR, "BAD_CLASS_ID", stem,
                                    f"ID lớp {class_id} nằm ngoài khoảng 0..{len(ds.classes) - 1}", line_number,
                                    {"class_id": class_id}))
                continue

            if box_width <= 0 or box_height <= 0:
                issues.append(Issue("label_format", ERROR, "BOX_ZERO", stem,
                                    "chiều rộng hoặc chiều cao box phải lớn hơn 0", line_number))
                continue

            left, top = cx - box_width / 2, cy - box_height / 2
            right, bottom = cx + box_width / 2, cy + box_height / 2
            overflow = max(0.0, -left, -top, right - 1.0, bottom - 1.0)
            if overflow > settings["overflow_tol"]:
                issues.append(Issue("label_format", ERROR, "BOX_OUT_OF_IMAGE", stem,
                                    f"box tràn khỏi ảnh {overflow:.6g}", line_number,
                                    {"overflow": overflow}))

            box = (cx, cy, box_width, box_height)
            if any(prev_class == class_id and iou_xywh(box, prev_box) > settings["dup_box_iou"]
                   for prev_class, prev_box in previous):
                issues.append(Issue("label_format", ERROR, "DUP_BOX", stem,
                                    "box trùng với box cùng lớp ở dòng trước", line_number))
            previous.append((class_id, box))

            if width is not None and min(box_width * width, box_height * height) < settings["min_box_px"]:
                issues.append(Issue("label_format", WARN, "BOX_TINY", stem,
                                    f"cạnh ngắn của box nhỏ hơn {settings['min_box_px']} px", line_number))
            if box_width * box_height > settings["max_box_frac"]:
                issues.append(Issue("label_format", WARN, "BOX_HUGE", stem,
                                    "box chiếm diện tích quá lớn của ảnh", line_number))

    return issues
