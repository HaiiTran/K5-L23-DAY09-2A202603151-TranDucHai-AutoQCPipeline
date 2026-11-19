"""BƯỚC 2/4 — Sửa tự động những lỗi bắt buộc mà máy sửa được AN TOÀN.   ★★

Test:  pytest tests/test_autofix.py -q

`fix(ds, issues, cfg) -> list[dict]`: duyệt `issues` (chỉ lỗi severity ERROR), sửa thẳng vào thư mục `ds`,
và trả về danh sách thay đổi; mỗi phần tử có khoá: image, line, action, before, after
(đây chính là file `03_fixes.csv` — bằng chứng pipeline đã làm gì, người có thể kiểm lại).

| code lỗi                                       | cách sửa                                    | action           |
|------------------------------------------------|---------------------------------------------|------------------|
| BAD_FORMAT, BAD_CLASS_ID, BOX_ZERO, DUP_BOX    | xoá dòng đó khỏi file nhãn                  | "drop_line"      |
| BOX_OUT_OF_IMAGE                               | cắt box về trong [0,1] (giữ nguyên lớp)     | "clip_box"       |
| MISSING_LABEL_FILE                             | KHÔNG sửa file (máy không thể bịa nhãn): ghi 1 dòng fix, before="(không có file)", after="chuyển người gán" | "needs_label" |
| BAD_CLASS_NAME                                 | ghi lại `names` trong data.yaml đúng `cfg["classes"]` | "rename_classes" |
| DUP_IMAGE_*, LEAK_TEST, CORRUPT_IMAGE, BAD_SIZE| xoá ảnh + nhãn khỏi `ds`                    | "remove_image"   |

Bẫy cần nghĩ tới (có test cho từng cái)
- Một file có NHIỀU dòng lỗi: số dòng trong `issues` là số dòng GỐC. Nếu xoá từng dòng một thì số dòng lệch.
  Gom theo file, rồi ghi lại MỘT lần.
- Sau khi cắt, box có thể không còn diện tích (nằm hẳn ngoài ảnh): lúc đó xoá dòng thay vì ghi box rỗng.
- Một dòng có 2 lỗi (vd. BOX_OUT_OF_IMAGE + DUP_BOX): xoá dòng thắng, chỉ ghi 1 fix `drop_line`, không ghi thêm `clip_box`. Dòng trống ở giữa file vẫn đếm vào số dòng gốc.
- Ảnh vừa bị xoá (DUP_IMAGE_*...) mà còn issue dòng của chính nó: bỏ qua êm, không được báo lỗi/chết.
- Không động tới lỗi WARN (cảnh báo là việc của người). Không sửa file ở `data/raw/` — chỉ sửa `ds`.
- Chạy lần 2 trên dữ liệu đã sửa phải không làm gì thêm (idempotent) — NGOẠI LỆ duy nhất: `needs_label` được ghi lại mỗi lần còn lỗi `MISSING_LABEL_FILE` (vì ảnh vẫn chưa có nhãn).

- `needs_label` KHÔNG tạo file nhãn rỗng (rỗng = "ảnh nền", khác với "chưa gán"). `review_queue` sẽ đẩy ảnh này lên đầu hàng đợi cho người.

Gợi ý: `yaml.safe_load / safe_dump`.
"""
from collections import defaultdict  # noqa: F401

import yaml  # noqa: F401

from ..common import ERROR, parse_yolo_line  # noqa: F401


def fix(ds, issues, cfg):
    drop_codes = {"BAD_FORMAT", "BAD_CLASS_ID", "BOX_ZERO", "DUP_BOX"}
    remove_codes = {"DUP_IMAGE_EXACT", "DUP_IMAGE_NEAR", "LEAK_TEST", "CORRUPT_IMAGE", "BAD_SIZE"}
    removed = set()
    drop_lines = defaultdict(set)
    clip_lines = defaultdict(set)
    needs_labels = set()
    rename_classes = False

    for issue in issues:
        if issue.severity != ERROR:
            continue
        if issue.code in remove_codes:
            removed.add(issue.image)
        elif issue.code in drop_codes and issue.line is not None:
            drop_lines[issue.image].add(issue.line)
        elif issue.code == "BOX_OUT_OF_IMAGE" and issue.line is not None:
            clip_lines[issue.image].add(issue.line)
        elif issue.code == "MISSING_LABEL_FILE":
            needs_labels.add(issue.image)
        elif issue.code == "BAD_CLASS_NAME":
            rename_classes = True

    changes = []

    # Image removal takes precedence over line edits for the same image.
    for stem in sorted(removed):
        image_paths = [p for p in ds.image_files() if p.stem == stem]
        label_path = ds.label_path(stem)
        if not image_paths and not label_path.exists():
            continue
        for path in image_paths:
            path.unlink(missing_ok=True)
        label_path.unlink(missing_ok=True)
        changes.append({"image": stem, "line": "", "action": "remove_image",
                        "before": "ảnh và nhãn hiện có", "after": "đã xóa khỏi dataset làm việc"})

    for stem in sorted(set(drop_lines) | set(clip_lines)):
        if stem in removed:
            continue
        path = ds.label_path(stem)
        if not path.is_file():
            continue
        original_text = path.read_text(encoding="utf-8", errors="replace")
        lines = original_text.splitlines()
        updated = list(lines)
        changed = False

        for line_number in sorted(drop_lines[stem] | clip_lines[stem]):
            index = line_number - 1
            if index < 0 or index >= len(lines) or not lines[index].strip():
                continue
            before = lines[index]

            # A mandatory drop always wins when the same source line has several errors.
            if line_number in drop_lines[stem]:
                updated[index] = None
                changes.append({"image": stem, "line": line_number, "action": "drop_line",
                                "before": before, "after": ""})
                changed = True
                continue

            try:
                class_id, cx, cy, width, height = parse_yolo_line(before)
            except ValueError:
                continue
            left, top = cx - width / 2, cy - height / 2
            right, bottom = cx + width / 2, cy + height / 2
            clipped_left, clipped_top = max(0.0, left), max(0.0, top)
            clipped_right, clipped_bottom = min(1.0, right), min(1.0, bottom)
            clipped_width = clipped_right - clipped_left
            clipped_height = clipped_bottom - clipped_top

            # A box wholly beyond an image edge has no area after clipping.
            if clipped_width <= 0 or clipped_height <= 0:
                updated[index] = None
                changes.append({"image": stem, "line": line_number, "action": "drop_line",
                                "before": before, "after": ""})
            else:
                clipped_cx = (clipped_left + clipped_right) / 2
                clipped_cy = (clipped_top + clipped_bottom) / 2
                after = " ".join(format(value, ".10g") for value in
                                 (class_id, clipped_cx, clipped_cy, clipped_width, clipped_height))
                if after == before:
                    continue
                updated[index] = after
                changes.append({"image": stem, "line": line_number, "action": "clip_box",
                                "before": before, "after": after})
            changed = True

        if changed:
            trailing_newline = original_text.endswith(("\n", "\r"))
            kept_lines = [line for line in updated if line is not None]
            path.write_text("\n".join(kept_lines) + ("\n" if trailing_newline else ""), encoding="utf-8")

    for stem in sorted(needs_labels - removed):
        if ds.image_path(stem) is not None and not ds.label_path(stem).exists():
            changes.append({"image": stem, "line": "", "action": "needs_label",
                            "before": "(không có file)", "after": "chuyển người gán"})

    if rename_classes:
        yaml_path = ds.yaml_path
        if yaml_path.exists():
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            if data is None:
                data = {}
            if not isinstance(data, dict):
                raise ValueError(f"nội dung YAML không phải mapping: {yaml_path}")
        else:
            data = {}
        correct_names = {index: name for index, name in enumerate(cfg["classes"])}
        if data.get("names") != correct_names:
            before = data.get("names", "(không có names)")
            data["names"] = correct_names
            yaml_path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
            changes.append({"image": "data.yaml", "line": "", "action": "rename_classes",
                            "before": str(before), "after": str(correct_names)})

    return changes
