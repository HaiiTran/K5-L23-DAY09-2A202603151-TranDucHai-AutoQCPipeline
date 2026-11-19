"""BƯỚC 4 — Cửa chặn: quyết định Release / Hold / Rework.   ★

Test:  pytest tests/test_gate.py -q

Cây quyết định Day 07 (slide Day 09: "Lỗi bắt buộc chặn pipeline; lỗi cảnh báo chuyển người xem"):

  còn ≥ 1 lỗi bắt buộc (severity ERROR)                          -> "Rework"
  không còn lỗi bắt buộc, nhưng tỉ lệ ẢNH còn cảnh báo
      >= cfg["gate"]["warn_ratio_hold"]                          -> "Hold"
  còn lại                                                        -> "Release"

Tỉ lệ cảnh báo = (số ẢNH khác nhau có ≥ 1 cảnh báo) / (tổng số ảnh).  Chú ý:
- chỉ đếm issue có `image` nằm trong `image_stems` (bỏ "<dataset>", "data.yaml");
- bỏ qua ảnh nằm trong `reviewed` (người đã xem, cảnh báo của ảnh đó coi như đã xử lý) — nhưng LỖI BẮT BUỘC thì không bao giờ được bỏ qua;
- mẫu số là số ảnh, không phải số issue.

Trả về dict: decision, n_errors, n_warn_images, n_images, warn_ratio (làm tròn 4 chữ số), reasons (list[str], giải thích bằng tiếng Việt, có số liệu).
"""
import math

from ..common import ERROR, WARN  # noqa: F401


def decide(issues, image_stems, cfg, reviewed=frozenset()):
    try:
        threshold = cfg["gate"]["warn_ratio_hold"]
    except (KeyError, TypeError) as exc:
        raise ValueError("thiếu cấu hình gate.warn_ratio_hold") from exc
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError("gate.warn_ratio_hold phải là số hữu hạn trong khoảng 0..1")

    stems = set(image_stems)
    reviewed_images = set(reviewed or ())
    n_images = len(stems)
    n_errors = 0
    warned_images = set()

    for issue in issues:
        if issue.severity == ERROR:
            # Lỗi bắt buộc luôn chặn, kể cả lỗi cấp dataset hoặc ảnh đã được duyệt.
            n_errors += 1
        elif issue.severity == WARN and issue.image in stems and issue.image not in reviewed_images:
            warned_images.add(issue.image)

    n_warn_images = len(warned_images)
    warn_ratio = n_warn_images / n_images if n_images else 0.0

    if n_errors:
        decision = "Rework"
        reasons = [f"Còn {n_errors} lỗi bắt buộc; cần sửa trước khi phát hành."]
    elif warn_ratio >= threshold:
        decision = "Hold"
        reasons = [
            f"Còn cảnh báo trên {n_warn_images}/{n_images} ảnh ({warn_ratio:.1%}), "
            f"đạt/vượt ngưỡng Hold {threshold:.1%}."
        ]
    else:
        decision = "Release"
        reasons = [
            f"Không còn lỗi bắt buộc; cảnh báo trên {n_warn_images}/{n_images} ảnh "
            f"({warn_ratio:.1%}) thấp hơn ngưỡng Hold {threshold:.1%}."
        ]

    return {
        "decision": decision,
        "n_errors": n_errors,
        "n_warn_images": n_warn_images,
        "n_images": n_images,
        "warn_ratio": round(warn_ratio, 4),
        "reasons": reasons,
    }
