import os
import numpy as np
import cv2
from utils.image_utils import process_images_with_padding


def test_process_images_with_padding():
    sample_dir = "source/image/samples/"
    files = [
        os.path.join(sample_dir, f)
        for f in [
            "sample_1_1.jpg",
            "sample_16_9.jpg",
            "sample_4_3.jpg",
            "sample_3_4.jpg",
            "sample_9_16.jpg",
        ]
    ]
    for f in files:
        assert os.path.exists(f), f"Missing sample image: {f}"
    # Test với target 1280x720
    imgs = process_images_with_padding(files, target_size=(1280, 720))
    assert len(imgs) == len(files)
    for i, img in enumerate(imgs):
        assert isinstance(img, np.ndarray)
        assert img.shape[1] == 1280 and img.shape[0] == 720
        # Nếu có padding thì kiểm tra đúng màu, nếu không thì chỉ cần đúng shape
        pad_mask = np.all(img == 0, axis=2)
        if pad_mask.sum() > 0:
            h, w = img.shape[:2]
            assert (
                np.all(img[0, :, :] == 0)
                or np.all(img[-1, :, :] == 0)
                or np.all(img[:, 0, :] == 0)
                or np.all(img[:, -1, :] == 0)
            )
        # Lưu output ra cùng thư mục với sample, thêm _padded vào tên
        out_path = files[i].replace(".jpg", "_padded.jpg")
        cv2.imwrite(out_path, img)
    print("All image processing tests passed and outputs saved.")
