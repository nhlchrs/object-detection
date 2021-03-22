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

import tensorflow.compat.v2 as tf
from tensorflow_examples.lite.model_maker.core import compat
from tensorflow_examples.lite.model_maker.core import test_util
from tensorflow_examples.lite.model_maker.core.data_util import object_detector_dataloader
from tensorflow_examples.lite.model_maker.core.export_format import ExportFormat
from tensorflow_examples.lite.model_maker.core.task import configs
from tensorflow_examples.lite.model_maker.core.task import object_detector
from tensorflow_examples.lite.model_maker.core.task.model_spec import object_detector_spec


class ObjectDetectorTest(tf.test.TestCase):

  def testEfficientDetLite0(self):
    # Gets model specification.
    hub_path = test_util.get_test_data_path('fake_effdet_lite0_hub')
    spec = object_detector_spec.EfficientDetModelSpec(
        model_name='efficientdet-lite0', uri=hub_path)

    # Prepare data.
    images_dir, annotations_dir, label_map = test_util.create_pascal_voc(
        self.get_temp_dir())
    data = object_detector_dataloader.DataLoader.from_pascal_voc(
        images_dir, annotations_dir, label_map)

    # Train the model.
    task = object_detector.create(data, spec, batch_size=1, epochs=1)

    # Evaluate trained model
    metrics = task.evaluate(data, batch_size=1)
    self.assertIsInstance(metrics, dict)
    self.assertGreaterEqual(metrics['AP'], 0)

    # Export the model to saved model.
    spec.config.model_dir = None  # Don't restore checkpoint.
    output_path = os.path.join(self.get_temp_dir(), 'saved_model')
    task.export(self.get_temp_dir(), export_format=ExportFormat.SAVED_MODEL)
    self.assertTrue(os.path.isdir(output_path))
    self.assertNotEqual(len(os.listdir(output_path)), 0)

    # Export the model to TFLite model.
    output_path = os.path.join(self.get_temp_dir(), 'float.tflite')
    task.export(
        self.get_temp_dir(),
        tflite_filename='float.tflite',
        export_format=ExportFormat.TFLITE)
    self.assertTrue(tf.io.gfile.exists(output_path))
    self.assertGreater(os.path.getsize(output_path), 0)

    # Export the model to quantized TFLite model.
    # TODO(b/175173304): Skips the test for stable tensorflow 2.4 for now since
    # it fails. Will revert this change after TF upgrade.
    if tf.__version__.startswith('2.4'):
      return
    output_path = os.path.join(self.get_temp_dir(), 'model_quantized.tflite')
    config = configs.QuantizationConfig.create_full_integer_quantization(
        data, is_integer_only=True)
    task.export(
        self.get_temp_dir(),
        tflite_filename='model_quantized.tflite',
        quantization_config=config,
        export_format=ExportFormat.TFLITE)
    self.assertTrue(os.path.isfile(output_path))
    self.assertGreater(os.path.getsize(output_path), 0)


if __name__ == '__main__':
  # Load compressed models from tensorflow_hub
  os.environ['TFHUB_MODEL_LOAD_FORMAT'] = 'COMPRESSED'
  compat.setup_tf_behavior(tf_version=2)
  tf.test.main()
