import csv
import numpy as np
import tensorflow as tf

import sys
sys.path.append('./utils')

from load_data import DataLoad

flags = tf.app.flags
flags.DEFINE_integer("width", 128, "width")
flags.DEFINE_integer("height", 128, "height")
flags.DEFINE_integer("layers", 128, "layers")
flags.DEFINE_integer("batch_size", 32, "batch size")
flags.DEFINE_integer("num_process", 1, "process number")
flags.DEFINE_bool("is_train", True, "is train")
flags.DEFINE_string("data_type", "stage1", "sample or stage1")
config = flags.FLAGS

def expand_last_dim(*input_data):
  res = []
  for in_data in input_data:
    res.append(np.expand_dims(in_data, axis=len(in_data.shape)))
  if len(res) == 1:
    return res[0]
  else:
    return res

def Weight(shape, name):
    return tf.Variable(name=name + "_Weights", 
                       initial_value=tf.truncated_normal(shape=shape, mean=0, stddev=0.1))

def Bias(shape, name):
    return tf.Variable(name=name + "_Bias",
                      initial_value=tf.constant(shape=shape, value=0.0))

def conv(x, convShape, name, strides=[1, 1, 1, 1]):
    w = Weight(convShape, name)
    b = Bias([convShape[3]], name)
    return (tf.nn.conv2d(input=x, filter=w, strides=strides,
                       padding='VALID',
                       name=name + "_2DConv") + b)

def pool(x, name):
    return tf.nn.max_pool(value=x, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1],
                         padding='SAME',
                         name=name + "_MaxPool")

# Parameters
batchSize = config.batch_size

imageSize = (128, 128, 128)
labelsSize = 1

#Making the Model here

#Make place for input
is_training = tf.placeholder(tf.bool)

labelsInput = tf.placeholder(shape=[batchSize, labelsSize],
                            dtype=tf.float32,
                            name="InputLabels")

imagesPlaceholder = tf.placeholder(shape=[batchSize, imageSize[0], imageSize[1], imageSize[2], 1],
                                  dtype=tf.float32,
                                  name="InputImages")

#"Consume" the depth dimension
x_images = tf.reshape(imagesPlaceholder, [-1, imageSize[1], imageSize[2], 1])

#convolution Layes
hidden_Conv1 = tf.nn.relu(tf.contrib.layers.batch_norm(conv(x_images, [3, 3, 1, 4], "hidden_Conv1"), is_training=is_training))
hidden_Pool1 = pool(hidden_Conv1, "hidden_Conv1")

hidden_Conv2 = tf.nn.relu(tf.contrib.layers.batch_norm(conv(hidden_Pool1, [3, 3, 4, 4], "hidden_Conv2"), is_training=is_training))
hidden_Pool2 = pool(hidden_Conv2, "hidden_Conv2")

hidden_Conv3 = tf.nn.relu(tf.contrib.layers.batch_norm(conv(hidden_Pool2, [3, 3, 4, 8], "hidden_Conv3"), is_training=is_training))
hidden_Pool3 = pool(hidden_Conv3, "hidden_Conv2")

hidden_Conv4 = tf.nn.relu(tf.contrib.layers.batch_norm(conv(hidden_Pool3, [3, 3, 8, 8], "hidden_Conv4"), is_training=is_training))
hidden_Pool4 = pool(hidden_Conv4, "hidden_Conv4")

hidden_Conv5 = tf.nn.relu(tf.contrib.layers.batch_norm(conv(hidden_Pool4, [3, 3, 8, 16], "hidden_Conv5"), is_training=is_training))
hidden_Pool5 = pool(hidden_Conv5, "hidden_Conv5")

hidden_Conv6 = tf.nn.relu(tf.contrib.layers.batch_norm(conv(hidden_Pool5, [3, 3, 16, 16], "hidden_Conv6"), is_training=is_training))
hidden_Pool6 = pool(hidden_Conv6, "hidden_Conv6")

flattened_vector = tf.reshape(hidden_Pool6, shape=[hidden_Pool6.get_shape()[0].value, 
                                                   hidden_Pool6.get_shape()[1].value * 
                                                   hidden_Pool6.get_shape()[2].value *
                                                   hidden_Pool6.get_shape()[3].value])
vector_expanded = tf.expand_dims(flattened_vector, 1)
bring_back = tf.reshape(vector_expanded, shape=[batchSize, -1, vector_expanded.get_shape()[2].value])
added_around_instance = tf.reduce_sum(bring_back, 1)

hidden_Dense1_weights = Weight([added_around_instance.get_shape()[1].value, 64], "hidden_Dense1")
hidden_Dense1_bias = Bias([1, 64], "hidden_Dense1")

output_Dense2_weights = Weight([64, labelsSize], "output")
output_Dense2_bias = Bias([1, labelsSize], "output")

hidden = tf.nn.relu(tf.matmul(added_around_instance, hidden_Dense1_weights) + hidden_Dense1_bias)
output = tf.matmul(hidden, output_Dense2_weights) + output_Dense2_bias

loss = tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(output, labelsInput))

# Optimizer.
optimizer = tf.train.AdamOptimizer(learning_rat=0.03, beta1=0.5)
grads = optimizer.compute_gradients(loss)
update_ops = tf.get_collection(tf.GraphKeys.UPDATE_OPS)
with tf.control_dependencies(update_ops):
  train_op = optimizer.apply_gradients(grads)

# Prediction
prediction = tf.sigmoid(output)


# Training
num_epochs = 50
sess_config = tf.ConfigProto()
sess_config.gpu_options.allow_growth = True
sess_config.allow_soft_placement=True

with tf.Session(config=sess_config) as session:
  tf.global_variables_initializer().run()
  print('Initialized')
  
  data_loader = DataLoad(config=config)

  for epoch in range(num_epochs):
    # Training
    data_loader.train()
    while data_loader.has_next_batch():
      train_data, train_label, _ = data_loader.next_batch()
      train_data, train_label = expand_last_dim(train_data, train_label)

      feed_dict = {imagesPlaceholder: train_data, labelsInput: train_label, is_training: True}
      _, l, preds = session.run([train_op, loss, prediction], feed_dict=feed_dict)
      print('labels: preds \n %s' % np.concatenate((train_label, preds), axis=1))
      print('Mini-batch loss: %f' % l)


    # Validation
    data_loader.validation()
    total_loss = 0
    count = 0
    while data_loader.has_next_batch():
      valid_data, valid_label, _ = data_loader.next_batch()
      valid_data, valid_label = expand_last_dim(valid_data, valid_label)

      feed_dict = {imagesPlaceholder: valid_data, labelsInput: valid_label, is_training: False}
      l = session.run(loss, feed_dict=feed_dict)
      batch_size = valid_data.shape[0]
      total_loss = total_loss + l * batch_size
      count = count + batch_size

    valid_loss = total_loss / count
    print('Validation loss is: %f', valid_loss)


  # Test predictions
  data_loader.test()
  pred_dict = {}
  while data_loader.has_next_batch():
    test_data, _, test_id = data_loader.next_batch()
    test_data = expand_last_dim(test_data)
    
    feed_dict = {imagesPlaceholder : test_data, is_training: False}
    preds = session.run(prediction, feed_dict=feed_dict)
    for i in range(test_data.shape[0]):
      pred_dict[test_id[i]] = preds[i][0]

  # TODO: write the predictions to file.
  print("Now update csv")
  with open('submission_multi_instance_3.csv', 'w') as f:
    writer = csv.writer(f)
    # write the header
    for row in {'id':'cancer'}.items():
      writer.writerow(row)
    # write the content
    for row in pred_dict.items():
      writer.writerow(row)
