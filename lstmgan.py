import tensorflow as tf
import numpy as np
import scipy.misc
import time

start = 1
current = 1
#images_train, text_train
def generate_next_batch(batch_size,frames):
	global start, current, images_train, text_train
	if current >= start:
		current = 0
		images_train, text_train = load_batches(100)
	images = images_train[current*batch_size:current*batch_size + batch_size]
	text = text_train[current*batch_size:current*batch_size + batch_size]
	current += 0
	return images, text

def load_batches(num):
	global start
	image = "bouncing_data/image_%d.npy"%(start)
	text_file = "bouncing_data/text_%d.npy"%(start)
	t = np.load(text_file)
	img = np.load(image)
	for i in range(num-1):
		image = "bouncing_data/image_%d.npy"%(start+i+1)
		text_file = "bouncing_data/text_%d.npy"%(start+i+1)
		t2 = np.load(text_file)
		im2 = np.load(image)
		img = np.concatenate([img,im2],axis=0)
		t = np.concatenate([t,t2],axis=0)
	im = np.ndarray(shape=[num*img.shape[0],img.shape[1],32,32,1])
	for i in range(img.shape[0]):
		for j in range(img.shape[1]):
			im[i,j] = scipy.misc.imresize(img[i,j].reshape([64,64]),(32,32)).reshape([32,32,1])
	return im, t

def batch_normalize(X, eps=1e-6):
	if X.get_shape().ndims == 4 :
		mean = tf.reduce_mean(X,[0,1,2])
		stddev = tf.reduce_mean(tf.square(X-mean),[0,1,2])
		X = (X - mean)/tf.sqrt(stddev + eps)
	elif X.get_shape().ndims == 2:
		mean = tf.reduce_mean(X,[0])
		stddev = tf.reduce_mean(tf.square(X-mean),[0])
		X = (X - mean)/tf.sqrt(stddev + eps)
	elif X.get_shape().ndims == 5:
		mean = tf.reduce_mean(X,[0,1,2,3])
		stddev = tf.reduce_mean(tf.square(X-mean),[0,1,2,3])	
		X = (X-mean)/tf.sqrt(stddev + eps)
	elif X.get_shape().ndims == 3:
		mean = tf.reduce_mean(X,[0,1])
		stddev = tf.reduce_mean(tf.square(X-mean),[0,1])	
		X = (X-mean)/tf.sqrt(stddev + eps)
	else:
		raise NoImplementationForSuchDimensions
	return X

def lrelu(X, leak = 0.2):
	f1 = (1 + leak)*0.5
	f2 = (1 - leak)*0.5
	return X*f1 + abs(X)*f2

def bce(o,t):
	o  = tf.clip_by_value(o,1e-5,-1e-5)
	return tf.reduce_mean(tf.nn.sigmoid_cross_entropy_with_logits(logits=o,labels=t))

class VideoGAN():
	def __init__ (self,batch_size = 25,image_shape = [32,32,1],embedding_size = 96,otext_embedding_size = 300,text_embedding_size=150,dim1 = 720, dim2 = 128, dim3 = 64,dim4 = 16, dim_channel = 1,frames = 20,name="videogan", max_len=20, actual_frames=12):
		self.batch_size = batch_size
		self.image_shape = image_shape
		self.embedding_size = embedding_size
		self.text_embedding_size = text_embedding_size
		self.dim1 = 2048
		self.dim2 = dim2
		self.dim3 = dim3
		self.dim4 = dim4
		self.dim_channel = dim_channel
		self.name = name
		self.actual_frames = actual_frames
		self.frames = frames
		self.max_len = max_len
		self.otext_embedding_size = otext_embedding_size
		self.dim_4 = image_shape[0] // 4
		self.embedding_channel = ((4*embedding_size) // self.dim_4) // self.dim_4
		self.dim_2 = image_shape[0] // 2
		self.image_input_size = image_shape[0]*image_shape[1]*image_shape[2]
		with tf.device("/gpu:0"):
			self.g_weight1 = tf.Variable(tf.random_normal([embedding_size + text_embedding_size, dim1], stddev = 0.2), name=(self.name+"_generator_weight1"))
			self.g_weight2 = tf.Variable(tf.random_normal([dim1 + text_embedding_size, dim2*self.dim_4*self.dim_4], stddev = 0.2), name=(self.name+"_generator_weight2"))
			self.g_weight3 = tf.Variable(tf.random_normal([5,5,dim3,dim2+text_embedding_size], stddev = 0.2), name=(self.name+"_generator_weight3"))
			self.g_weight4 = tf.Variable(tf.random_normal([5,5,dim4,dim3+text_embedding_size], stddev = 0.2), name=(self.name+"_generator_weight4"))
			self.g_weight5 = tf.Variable(tf.random_normal([3,3,dim4+text_embedding_size,dim_channel], stddev = 0.2), name=(self.name+"_generator_weight5"))
			self.g_weight6 = tf.Variable(tf.random_normal([2,2,self.dim3,self.embedding_channel],stddev = 0.2), name=(self.name+"_generator_weight6"))

			self.d_weight1 = tf.Variable(tf.random_normal([3,3,dim_channel+text_embedding_size, dim4],stddev = 0.2), name=(self.name+"_disc_weight1"))
			self.d_weight2 = tf.Variable(tf.random_normal([3,3,dim4+text_embedding_size, dim3],stddev = 0.2), name=(self.name+"_disc_weight2"))
			self.d_weight3 = tf.Variable(tf.random_normal([4,4,dim3+text_embedding_size, dim2],stddev = 0.2), name=(self.name+"_disc_weight3"))
			self.d_weight4 = tf.Variable(tf.random_normal([dim2*self.dim_4*self.dim_4+text_embedding_size, dim1],stddev = 0.2), name=(self.name+"_disc_weight4"))
			self.d_weight5 = tf.Variable(tf.random_normal([dim1+text_embedding_size,1],stddev = 0.2), name=(self.name+"_disc_weight5"))

			W = tf.Variable(tf.random_normal([4,1,self.embedding_size,self.embedding_size],stddev=0.2),name='%s_lstm_U'%(self.name))
			U = tf.Variable(tf.random_normal([4,1,self.embedding_size,self.embedding_size],stddev=0.2),name='%s_lstm_U'%(self.name))
			self.lstm_weightW = tf.Variable(tf.random_normal([4,1,self.embedding_size,self.embedding_size],stddev=0.2),name='%s_lstm_U'%(self.name))
			self.lstm_weightU = tf.Variable(tf.random_normal([4,1,self.embedding_size,self.embedding_size],stddev=0.2),name='%s_lstm_U'%(self.name))
			for i in range(self.batch_size-1):
				self.lstm_weightW = tf.concat(axis=1,values=[self.lstm_weightW,W])
				self.lstm_weightU = tf.concat(axis=1,values=[self.lstm_weightU,U])
	def build_model(self):
		with tf.device("/gpu:0"):
			embedding = tf.placeholder(tf.float32, [self.batch_size, self.embedding_size])
			text_embedding_raw = tf.placeholder(tf.float32, [self.batch_size, self.otext_embedding_size, self.max_len])
			r_video = tf.placeholder(tf.float32, [self.batch_size,self.frames] + self.image_shape)
			text_embedding_false = tf.placeholder(tf.float32,[self.batch_size,self.frames,self.text_embedding_size])
			# LSTM Cell

			text_embedding = self.generate_embedding_raw(text_embedding_raw)
			h4_,hidden,next_embedding = self.generate(embedding, text_embedding[:,:,0])
			
			self.init = ((tf.random_normal(stddev=0.5,shape=([self.batch_size,self.embedding_size,1]))),tf.random_normal(stddev=0.5,shape=([self.batch_size,self.embedding_size,1])))
			state = self.lstm(self.init, next_embedding)
			iterate_embedding = tf.reshape(state[0],shape=[self.batch_size,self.embedding_size])		
			h4 = tf.reshape(h4_,shape=[self.batch_size,1] + self.image_shape)
			g_image = tf.nn.sigmoid(h4_)
			real_value = self.discriminate(r_video[:,0], text_embedding[:,:,0])
			prob_real = tf.nn.sigmoid(real_value)
			fake_value = self.discriminate(g_image, text_embedding[:,:,0],flag=False,h2=hidden)
			prob_fake = tf.nn.sigmoid(fake_value)
			real_text = self.discriminate(r_video[:,0], text_embedding_false[:,0])
			prob_fake_text = tf.nn.sigmoid(real_text)
			for i in range(1,self.actual_frames):
				h4_,hidden,next_embedding = self.generate(iterate_embedding, text_embedding[:,:,i])
				state = self.lstm(state, next_embedding)
				iterate_embedding = batch_normalize(tf.reshape(state[0],shape=[self.batch_size,self.embedding_size]))
				g_image = tf.nn.sigmoid(h4_)
				real_value = self.discriminate(r_video[:,i], text_embedding[:,:,i])
				prob_real = tf.nn.sigmoid(real_value)*prob_real
				real_text = self.discriminate(r_video[:,i], text_embedding_false[:,i])
				prob_fake_text = prob_fake_text + tf.nn.sigmoid(real_text)-(tf.nn.sigmoid(real_text)*prob_fake_text)
				fake_value = self.discriminate(g_image, text_embedding[:,:,i],flag=False,h2=hidden)
				prob_fake = tf.nn.sigmoid(fake_value)+prob_fake - (tf.nn.sigmoid(fake_value)*prob_fake)
			# cost functions
			d_cost = -tf.reduce_mean(tf.log(prob_real) + tf.log(1. - prob_fake) + tf.log(1. - prob_fake_text))
			g_cost = -tf.reduce_mean(tf.log(prob_fake))

			return embedding, text_embedding_raw, text_embedding_false, r_video, d_cost, g_cost

	def lstm(self,prev,x):
		with tf.device("/gpu:0"):
			st_1, ct_1 = prev
			x = tf.reshape(x,shape=([self.batch_size,self.embedding_size,1]))
			i = tf.sigmoid(tf.matmul(self.lstm_weightU[0],x) + tf.matmul(self.lstm_weightW[0],st_1))
			f = tf.sigmoid(tf.matmul(self.lstm_weightU[1],x) + tf.matmul(self.lstm_weightW[1],st_1))
			o = tf.sigmoid(tf.matmul(self.lstm_weightU[2],x) + tf.matmul(self.lstm_weightW[2],st_1))
			g = tf.tanh(tf.matmul(self.lstm_weightU[3],x) + tf.matmul(self.lstm_weightW[3],st_1))
			ct = ct_1*f + g*i
			st = tf.tanh(ct)*o
			return (st,ct)

	def generate_embedding_raw(self,text_embedding):
		# naive attention
		with tf.device("/gpu:0"):
			conversion = tf.nn.max_pool(tf.reshape(text_embedding,shape=([self.batch_size,self.otext_embedding_size,self.max_len,1])),ksize=[1,2,2,1],strides=[1,2,1,1],padding='SAME')
			conv = tf.reshape(conversion,shape=[self.batch_size,self.text_embedding_size, self.max_len])
			self.attention = tf.Variable(tf.random_normal([self.max_len,self.frames],stddev=1.0),name="%s_disc_attention"%(self.name))
			attention = self.attention
			attention_mat = tf.reshape(attention,shape=[1,self.max_len,self.frames])
			attention_matr = tf.reshape(attention,shape=[1,self.max_len,self.frames])
			for t in range(1,self.batch_size):
				attention_matr = tf.concat(values=[attention_matr,attention_mat], axis=0)
			h = batch_normalize(tf.matmul(conv,attention_matr))
			return h

	def generate(self, embedding, text_embedding):
		with tf.device("/gpu:0"):
			ystack2 = tf.reshape(text_embedding, [self.batch_size, 1,1, self.text_embedding_size])
			embedding = tf.concat(axis=1, values=[embedding, text_embedding])
			h1 = tf.nn.relu(batch_normalize(tf.matmul(embedding, self.g_weight1)))
			h1 = tf.concat(axis=1, values=[h1, text_embedding])
			
			h2 = tf.nn.relu(batch_normalize(tf.matmul(h1,self.g_weight2)))
			h2 = tf.reshape(h2, [self.batch_size,self.dim_4,self.dim_4,self.dim2])
			h2 = tf.concat(axis=3,values=[h2,ystack2*tf.ones([self.batch_size,self.dim_4,self.dim_4,self.text_embedding_size])])
			
			output_shape1 = [self.batch_size,self.dim_2,self.dim_2,self.dim3]
			h3 = tf.nn.conv2d_transpose(h2,self.g_weight3,output_shape=output_shape1,strides=[1,2,2,1])
			h3 = tf.nn.relu(batch_normalize(h3))
			h3 = tf.concat(axis=3,values=[h3,ystack2*tf.ones([self.batch_size,self.dim_2,self.dim_2,self.text_embedding_size])])

			output_shape3 = [self.batch_size,self.image_shape[0],self.image_shape[1],self.dim4]
			h4 = tf.nn.relu(batch_normalize(tf.nn.conv2d_transpose(h3, self.g_weight4, output_shape=output_shape3, strides=[1,2,2,1])))
			h5 = tf.concat(axis=3,values=[h4,ystack2*tf.ones([self.batch_size,self.image_shape[0],self.image_shape[1],self.text_embedding_size])])
			
			output_shape2 = [self.batch_size] + list(self.image_shape)
			h6 = batch_normalize(tf.nn.conv2d(h5,self.g_weight5, strides=[1,1,1,1],padding='SAME'))
			
			text_embedding_size = self.text_embedding_size
			height1 = self.dim_2
			height2 = self.dim_4

			video_shape = list(self.image_shape)
			video_shape[2] += 150
			image_ = tf.concat(axis=3, values=[tf.nn.sigmoid(h6), ystack2*tf.ones([self.batch_size] + self.image_shape)])
			proc_image = batch_normalize(image_)
			h1 = batch_normalize(lrelu(tf.nn.conv2d(proc_image, self.d_weight1, strides=[1,2,2,1],padding='SAME')))
			h1_ = tf.concat(axis=3, values=[h1,ystack2*tf.ones([self.batch_size,height1,height1,text_embedding_size])])
			h2 = batch_normalize(lrelu(tf.nn.conv2d(h1_,self.d_weight2,strides=[1,2,2,1],padding='SAME')))
			h3 = tf.nn.conv2d(h2,self.g_weight6,strides=[1,2,2,1],padding='SAME')
			return h6 , h2, tf.reshape(h3,shape=[self.batch_size, self.embedding_size])

	def discriminate(self, image, text_embedding,flag=False,h2=None):
		with tf.device("/gpu:0"):
			text_embedding_size = self.text_embedding_size
			height1 = self.dim_2
			height2 = self.dim_4
			ystack2 = tf.reshape(text_embedding,tf.stack([self.batch_size, 1,1, text_embedding_size]))

			if not flag:
				video_shape = list(self.image_shape)
				video_shape[2] += 150
				image = tf.concat(axis=3, values=[image, ystack2*tf.ones([self.batch_size] + self.image_shape)])
				proc_image = batch_normalize(image)
				h1 = batch_normalize(lrelu(tf.nn.conv2d(proc_image, self.d_weight1, strides=[1,2,2,1],padding='SAME')))
				h1_ = tf.concat(axis=3, values=[h1,ystack2*tf.ones([self.batch_size,height1,height1,text_embedding_size])])
				h2 = batch_normalize(lrelu(tf.nn.conv2d(h1_,self.d_weight2,strides=[1,2,2,1],padding='SAME')))

			h3 = batch_normalize(tf.concat(axis=3,values=[h2, ystack2*tf.ones(shape=[self.batch_size,height2, height2, text_embedding_size])]))
			h4 = lrelu(tf.nn.conv2d(h3,self.d_weight3, strides=[1,1,1,1],padding='SAME'))
			h8 = tf.reshape(h4, [self.batch_size,-1])
			h9 = tf.concat(axis=1,values=[h8,text_embedding])
			h10 = lrelu(batch_normalize(tf.matmul(h9, self.d_weight4)))
			h11 = tf.concat(axis=1,values=[h10,text_embedding])
			h12 = lrelu(batch_normalize(tf.matmul(h11, self.d_weight5)))
			return h12

	def samples_generator(self):
		with tf.device("/gpu:0"):
			batch_size = self.batch_size
			embedding = tf.placeholder(tf.float32,[batch_size, self.embedding_size])
			text_embedding = tf.placeholder(tf.float32,[batch_size,self.otext_embedding_size, self.max_len])
			raw = self.generate_embedding_raw(text_embedding)
			trill = self.generate(embedding, raw[:,:,0])
			state = self.lstm(self.init, trill[2])
			iterate_embedding = tf.reshape(state[0],shape=([self.batch_size,self.embedding_size]))
			t = tf.reshape(trill[0],shape=[self.batch_size, 1] + self.image_shape)
			for i in range(self.batch_size - 1):
				trill = self.generate(iterate_embedding, raw[:,:,i])
				state = self.lstm(self.init, trill[2])
				iterate_embedding = tf.reshape(state[0],shape=([self.batch_size,self.embedding_size]))
				r = tf.reshape(trill[0],shape=[self.batch_size, 1] + self.image_shape)
				t = tf.concat([t,r],axis=1)	
			return embedding,text_embedding,t

def save_visualization(X,ep,nh_nw=(10,20),batch_size = 25, frames=20):
	h,w = 32,32
	Y = X.reshape(batch_size*frames, h,w,1)
	image = np.zeros([h*nh_nw[0], w*nh_nw[1],3])
	for n,x in enumerate(Y):
		j = n // nh_nw[1]
		i = n % nh_nw[1]
		image[j*h:j*h + h, i*w:i*w + w,:] = x
	scipy.misc.imsave(("bouncingmnist/sample_%d.jpg"%(ep+1)),image)


batch_size = 25
print("Built model")

epoch = 1000
learning_rate = 1e-3

gan = VideoGAN()
embedding, sentence, sentence_false, real_video, d_loss, g_loss = gan.build_model()
session = tf.InteractiveSession()

g_weight_list = [i for i in filter(lambda x: x.name.startswith("videogan_gen"),tf.trainable_variables())] 
d_weight_list = [i for i in filter(lambda x: x.name.startswith("videogan_disc"), tf.trainable_variables())] 
lstm_weight_list = [i for i in filter(lambda x: x.name.startswith("videogan_lstm"), tf.trainable_variables())] 
# optimizers
with tf.device("/gpu:0"):
	g_optimizer = tf.train.AdamOptimizer(learning_rate, beta1=0.4).minimize(g_loss, var_list=g_weight_list+lstm_weight_list)
	d_optimizer = tf.train.AdamOptimizer(learning_rate, beta1=0.4).minimize(d_loss, var_list=d_weight_list)

embedding_size = 96
text_embedding_size = 150
num_examples = 2000
epoch = 50
frames = 20

embedding_sample, sentence_sample, image_sample = gan.samples_generator()
sample_video, sample_text = generate_next_batch(batch_size,20)
tf.global_variables_initializer().run()
sample_embedding = np.random.uniform(-1,1,size=[batch_size,embedding_size]).astype(np.float32)
save_visualization(sample_video,0)

saver = tf.train.Saver()
#batch_size = 25

print("Starting Training")
start_time = time.time()
for ep in range(epoch):
	start = 1
	current = 1
	avg_g_loss_val = 0
	avg_d_loss_val = 0
	start_epoch = time.time()
	for t in range(num_examples):
		print("Running: %d"%(t+1))
		batch,batch_text = generate_next_batch(batch_size,20)
		random = np.random.uniform(-1,1,size=[batch_size,embedding_size]).astype(np.float32)
		feed_dict1 = {
			real_video : batch,
			embedding : random, 
			sentence : batch_text,
			sentence_false : np.random.uniform(size=(batch_size, frames ,text_embedding_size))
		}
		feed_dict2 = {
		#	real_video : batch,
			embedding : random, 
			sentence : batch_text
		}
		_, g_loss_val = session.run([g_optimizer, g_loss],feed_dict=feed_dict2)
		_, d_loss_val = session.run([d_optimizer, d_loss],feed_dict=feed_dict1)
		avg_g_loss_val += g_loss_val
		print(avg_g_loss_val)
		avg_d_loss_val += d_loss_val
		print(avg_d_loss_val)
		if t%5 == 0 and t > 0:
			print("Total time: " + str(time.time()-start_time))
			print("Epoch time: " + str(time.time() - start_epoch))
			print("Done with batches: " + str(t*batch_size) + " Loesses :: Generator: " + str(g_loss_val / 10) + " and Discriminator: " + str(d_loss_val / 10) + " = " + str(d_loss_val/10 + g_loss_val/10))
			avg_g_loss_val = 0
			avg_d_loss_val = 0
	print("Saving sample images and data for later testing: ")
	feed_dict = {
		embedding_sample : sample_embedding,
		sentence_sample : sample_text
	}
	gen_samples = session.run(image_sample,feed_dict=feed_dict)
	save_visualization(gen_samples, ep)
	print("Epoch: %d has been completed"%(ep + 1))
	print("Total time in this epoch: "  + str(time.time() - start_epoch))
	saver.save(session=session)
	print("Saved session")
