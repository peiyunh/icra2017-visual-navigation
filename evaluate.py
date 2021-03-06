#!/usr/bin/env python
# -*- coding: utf-8 -*-
import tensorflow as tf
import numpy as np
import random
import sys
import os
import math

from network import ActorCriticFFNetwork
from training_thread import A3CTrainingThread
from scene_loader import THORDiscreteEnvironment as Environment

from utils.ops import sample_action

from constants import ACTION_SIZE
from constants import CHECKPOINT_DIR
from constants import NUM_EVAL_EPISODES
from constants import VERBOSE

from constants import TASK_TYPE
# from constants import TASK_LIST
from constants import TRAIN_TASK_LIST, TEST_TASK_LIST

import ipdb

import time

from matplotlib import pyplot as plt
plt.ion()

if __name__ == '__main__':

  device = "/cpu:0" # use CPU for display tool
  network_scope = TASK_TYPE
  list_of_tasks = TRAIN_TASK_LIST
  list_of_tasks = {'avd_train_Home_02_1': ["1160"]}
  # list_of_tasks = {'avd_train_Office_01_1': ['217']}
  scene_scopes = list_of_tasks.keys()

  global_network = ActorCriticFFNetwork(action_size=ACTION_SIZE,
                                        device=device,
                                        network_scope=network_scope,
                                        scene_scopes=scene_scopes)

  sess = tf.Session()
  init = tf.global_variables_initializer()
  sess.run(init)

  saver = tf.train.Saver()
  checkpoint = tf.train.get_checkpoint_state(CHECKPOINT_DIR)

  if checkpoint and checkpoint.model_checkpoint_path:
    saver.restore(sess, checkpoint.model_checkpoint_path)
    print("checkpoint loaded: {}".format(checkpoint.model_checkpoint_path))
  else:
    print("Could not find old checkpoint")

  scene_stats = dict()
  for scene_scope in scene_scopes:
    print 'Scene %s' % scene_scope

    image_files = os.listdir(os.path.join('avd/rohit_data', scene_scope.replace('avd_train_',''), 'jpg_rgb'))

    scene_stats[scene_scope] = []
    for task_scope in list_of_tasks[scene_scope]:
      print 'Task %s: %s' % (task_scope, image_files[int(task_scope)])

      env = Environment({
        'scene_name': scene_scope,
        'terminal_state_id': int(task_scope)
      })
      ep_rewards = []
      ep_lengths = []
      ep_collisions = []

      scopes = [network_scope, scene_scope, task_scope]

      for i_episode in range(NUM_EVAL_EPISODES):

        env.reset()
        terminal = False
        ep_reward = 0
        ep_collision = 0
        ep_t = 0

        plt.figure(figsize=(15,5))
        plt.clf()
        colors = plt.get_cmap('viridis', 20).colors

        # plot the target
        ax = plt.subplot(1,3,2)
        ax.imshow(env.h5_file['observation'][env.terminal_state_id].astype(np.uint8))
        ax.axis('off')
        
        ax = plt.subplot(1,3,3)
        xs, zs, rs = env.h5_file['location'][:,0], env.h5_file['location'][:,1], env.h5_file['rotation']
        target_x, target_z = xs[env.terminal_state_id], zs[env.terminal_state_id]
        target_r = rs[env.terminal_state_id] * math.pi / 180
        # for (x,z,r) in zip(xs,zs,rs):
        #   ax4.plot(x, z, '.', color=[.5,.5,.5])
        #   ax4.quiver(x, z, 20*math.cos(r),20*math.sin(r),color=[.5,.5,.5])
        ax.plot(xs, zs, '.', color=[.5,.5,.5], markersize=0.05)
        ax.quiver(xs, zs, 60*np.cos(rs),60*np.sin(rs),color=[.5,.5,.5], width=0.05)
        ax.plot(target_x, target_z, 'g.', markersize=0.05)
        ax.quiver(target_x, target_z, 60*math.cos(target_r),60*math.sin(target_r),color='r', width=0.05)
        
        xmin, xmax = np.min(xs), np.max(xs)
        zmin, zmax = np.min(zs), np.max(zs)
        # print (xmin, xmax, zmin, zmax)
        
        while not terminal:
          print 'Current %d %s' % (env.current_state_id, image_files[env.current_state_id])
          print env.h5_file['location'][env.current_state_id]
          
          ax = plt.subplot(1,3,1)
          ax.imshow(env.observation.astype(np.uint8))
          ax.axis('off')

          pi_values = global_network.run_policy(sess, env.s_t, env.target, scopes)
          action = sample_action(pi_values)
          print(pi_values, action)
          env.step(action)
          env.update()

          # NOTE: visualize how agents navigate around
          # ax2 = plt.subplot(1,4,2)
          # ax2.imshow(env.observation.astype(np.uint8))
          ax = plt.subplot(1,3,3)
          # get value estimate
          # print v_value
          ax.plot(env.x, env.z, '.', markersize=0.05)
          r = env.r*math.pi/180
          ax.quiver(env.x,env.z,60*np.cos(r),60*np.sin(r),color=colors[np.min([ep_t,len(colors)-1])],width=0.05)
          ax.axis('off')
          ax.set_aspect('equal')
          # ax.autoscale(tight=True)
          # ax.axis('equal')
          # ax.axis([xmin, xmax, zmin, zmax])
          # print(xmin, xmax, zmin, zmax)
          plt.tight_layout()
          plt.draw()
          vis_dir = 'visualization/%s-%s-run%d' % (scene_scope, task_scope, i_episode)
          if not os.path.exists(vis_dir):
            os.makedirs(vis_dir)
          plt.savefig(os.path.join(vis_dir, 'iter%d.png'%ep_t), transparent=True, bbox_inches='tight', pad_inches=0)
          
          terminal = env.terminal
          if ep_t == 10000: break
          if env.collided: ep_collision += 1
          ep_reward += env.reward
          ep_t += 1

        ep_lengths.append(ep_t)
        ep_rewards.append(ep_reward)
        ep_collisions.append(ep_collision)
        if VERBOSE: print("episode #{} ends after {} steps".format(i_episode, ep_t))

        time.sleep(2)

      print('evaluation: %s %s' % (scene_scope, task_scope))
      print('mean episode reward: %.2f' % np.mean(ep_rewards))
      print('mean episode length: %.2f' % np.mean(ep_lengths))
      print('mean episode collision: %.2f' % np.mean(ep_collisions))

      scene_stats[scene_scope].extend(ep_lengths)

print('\nResults (average trajectory length):')
for scene_scope in scene_stats:
  print('%s: %.2f steps'%(scene_scope, np.mean(scene_stats[scene_scope])))
