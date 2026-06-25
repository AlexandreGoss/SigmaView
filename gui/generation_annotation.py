import os
import tifffile
import numpy as np
import logging
import pandas as pd
from tensorflow.keras.models import load_model
from skimage.util import view_as_windows
from skimage.measure import label, regionprops
from skimage.filters import threshold_otsu, apply_hysteresis_threshold
from skimage.morphology import remove_small_objects
from scipy.spatial import cKDTree
from scipy.optimize import linear_sum_assignment
import multiprocessing
import concurrent.futures
import argparse
from pathlib import Path
import tensorflow as tf
import zarr

os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
tf.get_logger().setLevel('ERROR')
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
max_workers = max(1, multiprocessing.cpu_count() // 2)

parser = argparse.ArgumentParser(description="Generate enhanced binary annotations with 4D tracking")
parser.add_argument("--data_dir", type=str, default=None, help="Directory containing TIFF files")
parser.add_argument("--unet_model_path", type=str, required=True, help="Path to U-Net model file")
parser.add_argument("--output_dir", type=str, required=True, help="Output directory for annotations")
parser.add_argument("--skeleton_channel", type=int, default=0, help="Skeleton channel index")
parser.add_argument("--tile_size", type=int, default=128, help="2D tile size for U-Net inference")
parser.add_argument("--overlap", type=int, default=16, help="Tile overlap in pixels")
parser.add_argument("--input_tif", type=str, default=None, help="Specific TIFF file to process")
parser.add_argument("--include_skeleton", action="store_true", help="Include skeleton channel in output")
parser.add_argument("--enhance_contrast", action="store_true", help="Enhance skeleton channel contrast")
parser.add_argument("--max_distance", type=float, default=25.0, help="Maximum distance for temporal tracking")
parser.add_argument("--adaptive_thresh", action="store_true", help="Use adaptive thresholding")
parser.add_argument("--min_spine_size", type=int, default=15, help="Minimum spine size (voxels)")
parser.add_argument("--connectivity", type=int, default=5, help="Connectivity for cleanup")
parser.add_argument("--hysteresis_low", type=float, default=0.4, help="Hysteresis low threshold")
parser.add_argument("--hysteresis_high", type=float, default=0.6, help="Hysteresis high threshold")
parser.add_argument("--save_prob_maps", action="store_true", help="Save probability maps")
parser.add_argument("--export_zarr", action="store_true", help="Export Zarr format for Napari")
args = parser.parse_args()


class SpineTracker:
    def __init__(self, max_distance=25.0, num_frames=None):
        self.max_distance = max_distance
        self.num_frames = num_frames
        logger.info(f"Initializing SpineTracker with max_distance={self.max_distance}, num_frames={self.num_frames}")
        self.next_id = 1
        self.tracked_spines = {}
        self.motion_history = []

    def label_3d_volume(self, binary_volume):
        labeled = label(binary_volume > 0, connectivity=2)
        cleaned = np.zeros_like(labeled)
        for region in regionprops(labeled):
            if region.area >= args.min_spine_size:
                cleaned[labeled == region.label] = region.label
        return label(cleaned > 0, connectivity=2)

    def estimate_global_motion(self, prev_volume, current_volume):
        prev_center = np.array(prev_volume.shape) / 2
        curr_center = np.array(current_volume.shape) / 2
        return curr_center - prev_center

    def track_spines(self, labeled_volumes):
        tracked_volumes = []
        for t, labeled_volume in enumerate(labeled_volumes):
            props = regionprops(labeled_volume)
            if t == 0:
                tracked_volume = labeled_volume
                self.tracked_spines[t] = {
                    prop.label: {'centroid': prop.centroid, 'volume': prop.area} 
                    for prop in props
                }
                self.motion_history.append(np.zeros(3))
            else:
                global_offset = self.estimate_global_motion(
                    labeled_volumes[t-1], labeled_volume)
                self.motion_history.append(global_offset)
                tracked_volume = self.associate_spines(
                    labeled_volume, props, t, global_offset)
            tracked_volumes.append(tracked_volume)
        return tracked_volumes

    def associate_spines(self, labeled_volume, props, t, global_offset):
        tracked_volume = np.zeros_like(labeled_volume)
        self.tracked_spines[t] = {}
        current_centroids = [prop.centroid - global_offset for prop in props]
        current_volumes = [prop.area for prop in props]
        if t == 0:
            for prop in props:
                tracked_volume[labeled_volume == prop.label] = self.next_id
                self.tracked_spines[t][self.next_id] = {
                    'centroid': prop.centroid,
                    'volume': prop.area
                }
                self.next_id += 1
            return tracked_volume
        prev_frames = [t-i for i in range(1, min(self.num_frames + 1, t + 1) if self.num_frames is not None else t + 1)]
        prev_centroids = []
        prev_volumes = []
        prev_labels = []
        for pt in prev_frames:
            if pt in self.tracked_spines:
                prev_info = self.tracked_spines[pt]
                prev_centroids.extend([v['centroid'] for v in prev_info.values()])
                prev_volumes.extend([v['volume'] for v in prev_info.values()])
                prev_labels.extend(list(prev_info.keys()))
        if not prev_centroids:
            for prop in props:
                tracked_volume[labeled_volume == prop.label] = self.next_id
                self.tracked_spines[t][self.next_id] = {
                    'centroid': prop.centroid,
                    'volume': prop.area
                }
                self.next_id += 1
            return tracked_volume
        similarity = np.zeros((len(current_centroids), len(prev_centroids)))
        for i, (c_cent, c_vol) in enumerate(zip(current_centroids, current_volumes)):
            for j, (p_cent, p_vol) in enumerate(zip(prev_centroids, prev_volumes)):
                dist = np.linalg.norm(c_cent - p_cent)
                vol_diff = abs(c_vol - p_vol) / max(c_vol, p_vol)
                similarity[i,j] = 0.7*dist + 0.3*vol_diff
        row_ind, col_ind = linear_sum_assignment(similarity)
        used_current = set()
        used_prev = set()
        for i, j in zip(row_ind, col_ind):
            if similarity[i, j] > self.max_distance * 1.5:
                logger.warning(f"Rejected association: similarity={similarity[i,j]}, threshold={self.max_distance * 1.5}, i={i}, j={j}")
                continue
            prop = props[i]
            tracked_volume[labeled_volume == prop.label] = prev_labels[j]
            self.tracked_spines[t][prev_labels[j]] = {
                'centroid': prop.centroid,
                'volume': prop.area
            }
            used_current.add(i)
            used_prev.add(j)
        for i, prop in enumerate(props):
            if i not in used_current:
                tracked_volume[labeled_volume == prop.label] = self.next_id
                self.tracked_spines[t][self.next_id] = {
                    'centroid': prop.centroid,
                    'volume': prop.area
                }
                self.next_id += 1
        return tracked_volume


class AnnotationGenerator:
    def __init__(self, args):
        self.args = args
        self.unet_model = load_model(args.unet_model_path, compile=False)
        self.tile_size = args.tile_size
        self.overlap = args.overlap
        self.tracker = None
        os.makedirs(args.output_dir, exist_ok=True)

    def find_optimal_threshold(self, predictions):
        flat_preds = predictions.flatten()
        mask = flat_preds > 0.1
        return threshold_otsu(flat_preds[mask]) if mask.any() else 0.5

    def clean_binary(self, binary):
        return remove_small_objects(
            binary.astype(bool), 
            min_size=self.args.min_spine_size,
            connectivity=self.args.connectivity
        ).astype(np.uint8) * 255

    def process_slice(self, slice_2d):
        step = self.tile_size - self.overlap
        pad_h = (step - (slice_2d.shape[0] % step)) % step
        pad_w = (step - (slice_2d.shape[1] % step)) % step
        slice_padded = np.pad(slice_2d, ((0, pad_h), (0, pad_w)), mode='constant')
        tiles = view_as_windows(slice_padded, (self.tile_size, self.tile_size), step=step)
        n_tiles = tiles.shape[0] * tiles.shape[1]
        tiles = tiles.reshape(-1, self.tile_size, self.tile_size, 1).astype(np.float32)
        preds = self.unet_model.predict(tiles, batch_size=min(16, n_tiles), verbose=0)[..., 1]
        output = np.zeros(slice_padded.shape, dtype=np.float32)
        count = np.zeros(slice_padded.shape, dtype=np.float32)
        idx = 0
        for i in range(0, slice_padded.shape[0] - self.tile_size + 1, step):
            for j in range(0, slice_padded.shape[1] - self.tile_size + 1, step):
                output[i:i+self.tile_size, j:j+self.tile_size] += preds[idx]
                count[i:i+self.tile_size, j:j+self.tile_size] += 1
                idx += 1
        prob_map = output / (count + 1e-10)
        if self.args.adaptive_thresh:
            binary = prob_map > self.find_optimal_threshold(prob_map)
        else:
            binary = apply_hysteresis_threshold(
                prob_map,
                self.args.hysteresis_low,
                self.args.hysteresis_high
            )
        binary = self.clean_binary(binary)
        return binary[:slice_2d.shape[0], :slice_2d.shape[1]], prob_map[:slice_2d.shape[0], :slice_2d.shape[1]]

    def save_output(self, data, output_path):
        try:
            metadata = {
                'axes': 'TZCYX',
                'SigmaView': 'Dendritic Spine Analysis',
                'Parameters': str({
                    'min_spine_size': self.args.min_spine_size,
                    'max_distance': self.args.max_distance,
                    'adaptive_thresh': self.args.adaptive_thresh
                }),
                'mricia-label-channel': 4
            }
            logger.info(f"Multi-channel stack dimensions: {data.shape}")
            tifffile.imwrite(
                output_path,
                data,
                imagej=True,
                metadata=metadata,
                compression='zlib'
            )
            logger.info(f"Multi-channel file saved: {output_path}")
        except Exception as e:
            logger.error(f"Save error: {str(e)}")
            raise

    def export_zarr(self, volumes, output_path):
        try:
            store = zarr.DirectoryStore(output_path)
            root = zarr.group(store=store)
            root.create_dataset('binary', data=[v[..., 0] for v in volumes], chunks=True)
            root.create_dataset('labels', data=[v[..., 1] for v in volumes], chunks=True)
            if volumes[0].shape[2] > 2:
                root.create_dataset('skeleton', data=[v[..., 2] for v in volumes], chunks=True)
            logger.info(f"Zarr export successful: {output_path}")
        except Exception as e:
            logger.error(f"Zarr export error: {str(e)}")

    def save_spine_data_to_csv(self, output_path):
        try:
            spine_data = []
            for t in self.tracker.tracked_spines:
                for spine_id, props in self.tracker.tracked_spines[t].items():
                    spine_data.append({
                        'Frame': t,
                        'Spine_ID': spine_id,
                        'Centroid_Z': props['centroid'][0],
                        'Centroid_Y': props['centroid'][1],
                        'Centroid_X': props['centroid'][2],
                        'Volume': props['volume']
                    })
            df = pd.DataFrame(spine_data)
            csv_path = output_path.with_suffix('.csv')
            df.to_csv(csv_path, index=False)
            logger.info(f"CSV file saved: {csv_path}")
        except Exception as e:
            logger.error(f"CSV save error: {str(e)}")

    def process_image(self, tif_path):
        logger.info(f"Processing {tif_path.name}")
        try:
            img = tifffile.imread(tif_path)
            if img.ndim != 5:
                logger.error(f"Unsupported format: {img.ndim}D (expected 5D TZCYX)")
                return
        except Exception as e:
            logger.error(f"Read error {tif_path.name}: {str(e)}")
            return
        num_frames, z_slices, num_channels, height, width = img.shape
        logger.info(f"Detected frames: {num_frames}")
        self.tracker = SpineTracker(max_distance=self.args.max_distance, num_frames=num_frames)

        def process_frame(t):
            logger.info(f"Processing frame {t+1}/{num_frames}")
            volume = img[t, :, self.args.skeleton_channel, :, :]
            frame_binary = []
            frame_probs = []
            for z in range(z_slices):
                binary, prob_map = self.process_slice(volume[z])
                frame_binary.append(binary)
                frame_probs.append(prob_map)
            return np.stack(frame_binary), np.stack(frame_probs)

        max_workers = max(1, multiprocessing.cpu_count() // 2)
        logger.info(f"Using {max_workers} parallel workers")
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(process_frame, range(num_frames)))

        binary_volumes = [r[0] for r in results]
        prob_volumes = [r[1] for r in results] if self.args.save_prob_maps else []

        labeled_volumes = [self.tracker.label_3d_volume(binary > 0) for binary in binary_volumes]
        tracked_volumes = self.tracker.track_spines(labeled_volumes)

        output_volumes = []
        for t, labeled_volume in enumerate(tracked_volumes):
            frame_volumes = []
            for z in range(z_slices):
                skeleton = img[t, z, self.args.skeleton_channel, :, :].astype(np.float32)
                if self.args.enhance_contrast:
                    p1, p99 = np.percentile(skeleton, (1, 99))
                    skeleton = np.clip((skeleton - p1) / (p99 - p1 + 1e-10), 0, 1)
                skeleton = (skeleton * 255).astype(np.uint8)
                input_channel_1 = img[t, z, 1, :, :].astype(np.uint8)
                binary = binary_volumes[t][z].astype(np.uint8)
                label = labeled_volume[z].astype(np.uint16)
                frame_volumes.append(np.stack([skeleton, input_channel_1, binary, label], axis=0))
            output_volumes.append(np.stack(frame_volumes, axis=0))

        output_volumes = np.array(output_volumes)
        base_name = Path(self.args.output_dir) / f"tracked_{tif_path.stem}"
        self.save_output(output_volumes, base_name.with_suffix('.tif'))

        if self.args.save_prob_maps and prob_volumes:
            prob_path = base_name.with_name(f"{base_name.stem}_probs.tif")
            tifffile.imwrite(
                prob_path,
                (np.array(prob_volumes) * 65535).astype(np.uint16),
                imagej=True
            )
        if self.args.export_zarr:
            self.export_zarr(output_volumes, base_name.with_suffix('.zarr'))
        self.save_spine_data_to_csv(base_name)


def main():
    generator = AnnotationGenerator(args)
    if args.input_tif:
        tif_path = Path(args.input_tif)
        if tif_path.exists():
            generator.process_image(tif_path)
        else:
            logger.error(f"File {args.input_tif} not found")
    else:
        data_dir = Path(args.data_dir)
        if data_dir.exists():
            for tif_file in data_dir.glob("*.tif"):
                generator.process_image(tif_file)
        else:
            logger.error(f"Directory {args.data_dir} not found")

if __name__ == "__main__":
    main()
