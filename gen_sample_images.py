import cv2
import os


def gen_sample_images(src_path):
    img = cv2.imread(src_path)
    if img is None:
        raise FileNotFoundError(f"Image not found: {src_path}")
    h, w = img.shape[:2]
    out_dir = "source/image/samples/"
    os.makedirs(out_dir, exist_ok=True)
    # 16:9 landscape
    img_16_9 = cv2.resize(img, (1280, 720), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(out_dir, "sample_16_9.jpg"), img_16_9)
    # 4:3 landscape
    img_4_3 = cv2.resize(img, (800, 600), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(out_dir, "sample_4_3.jpg"), img_4_3)
    # 1:1 square
    min_side = min(w, h)
    center = (w // 2, h // 2)
    img_1_1 = img[
        center[1] - min_side // 2 : center[1] + min_side // 2,
        center[0] - min_side // 2 : center[0] + min_side // 2,
    ]
    img_1_1 = cv2.resize(img_1_1, (600, 600), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(out_dir, "sample_1_1.jpg"), img_1_1)
    # 9:16 portrait
    img_9_16 = cv2.resize(img, (405, 720), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(out_dir, "sample_9_16.jpg"), img_9_16)
    # 3:4 portrait
    img_3_4 = cv2.resize(img, (450, 600), interpolation=cv2.INTER_AREA)
    cv2.imwrite(os.path.join(out_dir, "sample_3_4.jpg"), img_3_4)
    print("Sample images generated in", out_dir)


if __name__ == "__main__":
    gen_sample_images("source/image/sample.jpg")
