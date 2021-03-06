import tensorflow as tf

def _variable_on_cpu(name, shape, initializer):
	"""Helper to create a Variable stored on CPU memory."""
	with tf.device('/cpu:0'):
		var = tf.get_variable(name, shape, initializer=initializer)
		print(var)
	return var

def _variable_with_weight_decay(name, shape, wd):
	var = _variable_on_cpu(name, shape, tf.contrib.layers.xavier_initializer())
	if wd is not None:
		weight_decay = tf.mul(tf.nn.l2_loss(var), wd, name='weight_loss')
		tf.add_to_collection('losses', weight_decay)
	return var

def _conv2d(x, w, b, strides = [1,1,1,1]):
    return tf.nn.bias_add(tf.nn.conv2d(x,w,strides=strides, padding = 'SAME'), b)

def _dconv2d(x, w, b, output_shape, strides = [1,1,1,1]):
    return tf.nn.bias_add(tf.nn.conv2d_transpose(x, w, output_shape, strides), b)

def _unpooling(x, output_size):
    # NEAREST_NEIGHBOR resize
    return tf.image.resize_images(x, output_size[1], output_size[2],1)

def _add_leaky_relu(hl_tensor, leaky_param):
    return tf.maximum(hl_tensor, tf.mul(leaky_param, hl_tensor))

def inference1(data):
    data_shape_l = data.get_shape().as_list()
    with tf.variable_scope('conv1') as scope:
        weights = _variable_with_weight_decay('weights', shape=[3, 3, 3, 32],wd=0.0)
        biases = _variable_on_cpu('biases', [32], tf.constant_initializer(0.0))
        h_conv1 = _conv2d(data, weights, biases, [1,2,2,1])
      
    with tf.variable_scope('conv2') as scope:
        weights = _variable_with_weight_decay('weights', shape=[3, 3, 32, 32],wd=0.0)
        biases = _variable_on_cpu('biases', [32], tf.constant_initializer(0.0))
        h_conv2 = _conv2d(h_conv1, weights, biases, [1,1,1,1])

    with tf.variable_scope('deconv1') as scope:
        weights = _variable_with_weight_decay('weights', shape=[3, 3, 32, 32],wd=0.0)
        biases = _variable_on_cpu('biases', [32], tf.constant_initializer(0.0))
        output_shape = tf.pack(h_conv1.get_shape().as_list())
        h_dconv1 = _dconv2d(h_conv2, weights, biases, output_shape, [1,1,1,1])

    with tf.variable_scope('deconv2') as scope:
        weights = _variable_with_weight_decay('weights', shape=[3, 3, 3, 32],wd=0.0)
        biases = _variable_on_cpu('biases', [3], tf.constant_initializer(0.0))
        output_shape = tf.pack(data_shape_l)
        h_dconv2 = _dconv2d(h_dconv1, weights, biases, output_shape, [1,2,2,1])

    # with tf.variable_scope('deconv1') as scope:
    #     weights = _variable_with_weight_decay('weights', shape=[3, 3, 3, 32],
    #                                        stddev=1e-4, wd=0.0)
    #     biases = _variable_on_cpu('biases', [3], tf.constant_initializer(0.0))
    #     output_shape = tf.pack(data_shape_l)
    #     h_dconv1 = _dconv2d(h_conv1, weights, biases, output_shape, [1,2,2,1])
    return h_dconv2


def inference2(feature, feature_dim, label_dim, keep_prob = 1.0):
	feature_drop = tf.nn.dropout(feature,keep_prob)	
	with tf.variable_scope("fc") as scope:
		weights = _variable_with_weight_decay("weight", [feature_dim, label_dim], 0.001)
		biases = _variable_on_cpu("biases", [label_dim], tf.constant_initializer(0.0))
		fc = tf.nn.bias_add(tf.matmul(feature_drop, weights), biases)
	return fc

def inference3(feature, ksize, cell_c, label_c, keep_prob = 1.0):
	feature_drop = tf.nn.dropout(feature, keep_prob)	
	with tf.variable_scope("conv") as scope:
		#weights = _variable_with_weight_decay("weights", [ksize, ksize, cell_c, label_c], 0.0)
		weights = tf.Variable(tf.truncated_normal([ksize, ksize, cell_c, label_c], -0.1, 0.1))
		biases = tf.Variable(tf.zeros([label_c]))
		# weights = tf.Variable(tf.contrib.layers.xavier_initializer())
		# biases = _variable_on_cpu("biases", [label_c], tf.constant_initializer(0.0))
		cn1 = _conv2d(feature, weights, biases)
	return cn1

def loss1(infer, labels, scope = None):
	with tf.name_scope(scope or "l2_loss") as scope:
		l2_norm_loss = tf.reduce_mean(tf.square(infer - labels))
		tf.add_to_collection('losses', l2_norm_loss)

	return tf.add_n(tf.get_collection('losses'), name = 'total_loss')

def loss2(classify_res, labels):
    cross_entropy = tf.nn.softmax_cross_entropy_with_logits(classify_res,labels,name='xentropy')
    loss = tf.reduce_mean(cross_entropy, name='xentropy_mean')
    tf.add_to_collection('losses', loss)
    return tf.add_n(tf.get_collection('losses'), name = 'total_loss')

def training1(loss, learning_rate, global_step):
    optimizer = tf.train.AdamOptimizer(learning_rate, epsilon = 1.0)
    train_op = optimizer.minimize(loss, global_step = global_step)
    ema = tf.train.ExponentialMovingAverage(decay=0.9999)
    maintain_average_op = ema.apply(tf.trainable_variables())

    with tf.control_dependencies([train_op]):
        train_op_with_ema = tf.group(maintain_average_op)

    return train_op_with_ema
