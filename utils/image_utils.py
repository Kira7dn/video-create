import cv2


def process_images_with_padding(
    image_paths, target_size=(1280, 720), pad_color=(0, 0, 0)
):
    """
    Load, resize và padding ảnh về đúng target_size (w, h), giữ nguyên tỉ lệ, trả về list numpy array.
    Đảm bảo kích thước chia hết cho 2 để tương thích với H.264 codec.
    """
    processed = []
    target_w, target_h = target_size

    # Ensure target size is divisible by 2 for H.264 compatibility
    target_w = target_w - (target_w % 2)
    target_h = target_h - (target_h % 2)

    for i, path in enumerate(image_paths):
        img = cv2.imread(path)
        if img is None:
            raise FileNotFoundError(f"Image not found or unreadable: {path}")
        h, w = img.shape[:2]

        scale = min(target_w / w, target_h / h)
        new_w, new_h = int(w * scale), int(h * scale)

        # Ensure resized dimensions are also even
        new_w = new_w - (new_w % 2)
        new_h = new_h - (new_h % 2)

        resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
        pad_left = (target_w - new_w) // 2
        pad_right = target_w - new_w - pad_left
        pad_top = (target_h - new_h) // 2
        pad_bottom = target_h - new_h - pad_top

        padded = cv2.copyMakeBorder(
            resized,
            pad_top,
            pad_bottom,
            pad_left,
            pad_right,
            borderType=cv2.BORDER_CONSTANT,
            value=pad_color,
        )

        processed.append(padded)
    return processed
