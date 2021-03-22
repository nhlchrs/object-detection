# Copyright 2020 The TensorFlow Authors. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os

import numpy as np
from scipy.io import wavfile
import tensorflow.compat.v2 as tf
from tensorflow_examples.lite.model_maker.core import compat
from tensorflow_examples.lite.model_maker.core.data_util import audio_dataloader
from tensorflow_examples.lite.model_maker.core.export_format import ExportFormat
from tensorflow_examples.lite.model_maker.core.task import audio_classifier
from tensorflow_examples.lite.model_maker.core.task.model_spec import audio_spec


class BrowserFFTWithoutPreprocessing(audio_spec.BrowserFFTSpec):

  def preprocess_ds(self, ds, is_training=False):
    _ = is_training

    @tf.function
    def _crop(wav, label):
      wav = wav[:self.expected_waveform_len]
      return wav, label

    ds = ds.map(_crop)
    return ds


def write_sample(root,
                 category,
                 file_name,
                 sample_rate,
                 duration_sec,
                 dtype=np.int16):
  os.makedirs(os.path.join(root, category), exist_ok=True)
  xs = np.random.rand(int(sample_rate * duration_sec),) * (1 << 15)
  xs = xs.astype(dtype)
  full_path = os.path.join(root, category, file_name)
  wavfile.write(full_path, sample_rate, xs)
  return full_path


class AudioClassifierTest(tf.test.TestCase):

  def testBrowserFFT(self):

    temp_folder = self.get_temp_dir()
    cat1 = write_sample(temp_folder, 'cat', '1.wav', 44100, duration_sec=1)
    cat2 = write_sample(temp_folder, 'cat', '2.wav', 44100, duration_sec=2)
    dog1 = write_sample(temp_folder, 'dog', '1.wav', 44100, duration_sec=3)
    dog2 = write_sample(temp_folder, 'dog', '2.wav', 44100, duration_sec=4)
    index_to_labels = ['cat', 'dog']

    np.random.seed(123)
    tf.random.set_seed(123)

    # Prepare data.
    spec = audio_spec.BrowserFFTSpec()
    ds = tf.data.Dataset.from_tensor_slices(([cat1, cat2, dog1,
                                              dog2], [0, 0, 1, 1]))
    data_loader = audio_dataloader.DataLoader(ds, len(ds), index_to_labels,
                                              spec)

    # Train a floating point model.
    task = audio_classifier.create(data_loader, spec, batch_size=1, epochs=15)

    # Evaluate trained model
    _, acc = task.evaluate(data_loader)
    # Better than random guessing.
    self.assertGreater(acc, .5)

    # Export the model to saved model.
    output_path = os.path.join(spec.model_dir, 'saved_model')
    task.export(spec.model_dir, export_format=ExportFormat.SAVED_MODEL)
    self.assertTrue(os.path.isdir(output_path))
    self.assertNotEqual(len(os.listdir(output_path)), 0)

    # Export the model to TFLite.
    output_path = os.path.join(spec.model_dir, 'float.tflite')
    task.export(
        spec.model_dir,
        tflite_filename='float.tflite',
        export_format=ExportFormat.TFLITE)
    self.assertTrue(tf.io.gfile.exists(output_path))
    self.assertGreater(os.path.getsize(output_path), 0)

    # Evaluate accurarcy on TFLite model.

    # Create a new dataset without preprocessing since preprocessing has been
    # packaged inside TFLite model.
    spec = BrowserFFTWithoutPreprocessing()
    tflite_dataloader = audio_dataloader.DataLoader(ds, len(ds),
                                                    index_to_labels, spec)

    # Evaluate accurarcy on float model.
    result = task.evaluate_tflite(output_path, tflite_dataloader)
    self.assertGreaterEqual(result['accuracy'], .5)


if __name__ == '__main__':
  # Load compressed models from tensorflow_hub
  os.environ['TFHUB_MODEL_LOAD_FORMAT'] = 'COMPRESSED'
  compat.setup_tf_behavior(tf_version=2)
  tf.test.main()
