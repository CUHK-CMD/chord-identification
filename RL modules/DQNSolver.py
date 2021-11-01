from collections import deque
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import Dense, Input, Flatten
from tensorflow.keras.optimizers import Adam
from tensorflow.keras import backend as K
import random
import tqdm
from gym import Env
from gym.spaces import Discrete, Box
import numpy as np
import math
from itertools import combinations
from datetime import datetime


def huber_loss(a, b, in_keras=True):
    error = a - b
    quadratic_term = error * error / 2
    linear_term = abs(error) - 1 / 2
    use_linear_term = abs(error) > 1.0
    if in_keras:
        # Keras won't let us multiply floats by booleans, so we explicitly cast the booleans to floats
        use_linear_term = K.cast(use_linear_term, "float32")
    return use_linear_term * linear_term + (1 - use_linear_term) * quadratic_term


class DQNSolver:
    def __init__(
        self,
        env,
        n_episodes=1000,
        max_env_steps=None,
        gamma=1.0,
        epsilon=1.0,
        epsilon_min=0.01,
        epsilon_log_decay=0.999,
        alpha=0.01,
        tau=0.125,
        alpha_decay=0.005,
        batch_size=64,
    ):
        self.env = env
        self.memory = deque(maxlen=10000)
        self.memory1 = deque(maxlen=10000)
        self.memory2 = deque(maxlen=10000)
        self.memory3 = deque(maxlen=10000)
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_log_decay
        self.alpha = alpha
        self.tau = tau
        self.alpha_decay = alpha_decay
        self.n_episodes = n_episodes
        self.batch_size = batch_size
        if max_env_steps is not None:
            self.env._max_episode_steps = max_env_steps

        # Init model
        state_input = Input(shape=self.env.observation_space.shape)
        h2 = Dense(48, activation="ReLU")(state_input)
        h3 = Dense(24, activation="ReLU")(h2)
        output = Dense(2, activation="linear")(h3)
        self.model = Model(inputs=state_input, outputs=output)
        adam = Adam(learning_rate=self.alpha)
        self.model.compile(loss=huber_loss, optimizer=adam)
        # Target model (Basically the same thing)
        state_input2 = Input(shape=self.env.observation_space.shape)
        h22 = Dense(48, activation="ReLU")(state_input2)
        h32 = Dense(24, activation="ReLU")(h22)
        output2 = Dense(2, activation="linear")(h32)
        self.target_model = Model(inputs=state_input2, outputs=output2)
        adam2 = Adam(learning_rate=self.alpha)
        self.target_model.compile(loss=huber_loss, optimizer=adam2)

    def remember(self, state, action, reward, next_state, done):
        if reward == 1 and action == 1:
            self.memory.append((state, action, reward, next_state, done))
        elif reward == 1 and action == 0:
            self.memory1.append((state, action, reward, next_state, done))
        elif reward == -1 and action == 0:
            self.memory2.append((state, action, reward, next_state, done))
        else:
            self.memory3.append((state, action, reward, next_state, done))

    def choose_action(self, state, epsilon):
        state = state.reshape((1, 12 * 2 + 1))
        return (
            self.env.action_space.sample()
            if (np.random.random() <= epsilon)
            else np.argmax(self.model.predict(state))
        )

    def get_epsilon(self, t):
        return max(
            self.epsilon_min,
            min(self.epsilon, 1.0 - math.log10((t + 1) * self.epsilon_decay)),
        )

    def replay(self, batch_size):
        x_batch, y_batch = [], []
        minibatch = random.sample(
            self.memory, min(len(self.memory), int(batch_size * 0.25))
        )
        for state, action, reward, next_state, done in minibatch:
            state = state.reshape((1, 12 * 2 + 1))
            next_state = next_state.reshape((1, 12 * 2 + 1))
            y_target = self.target_model.predict(state)
            y_target[0][action] = (
                reward
                if done
                else reward
                + self.gamma * np.max(self.target_model.predict(next_state)[0])
            )
            x_batch.append(state[0])
            y_batch.append(y_target[0])
        minibatch2 = random.sample(
            self.memory1, min(len(self.memory1), int(batch_size * 0.25))
        )
        for state, action, reward, next_state, done in minibatch2:
            state = state.reshape((1, 12 * 2 + 1))
            next_state = next_state.reshape((1, 12 * 2 + 1))
            y_target = self.target_model.predict(state)
            y_target[0][action] = (
                reward
                if done
                else reward
                + self.gamma * np.max(self.target_model.predict(next_state)[0])
            )
            x_batch.append(state[0])
            y_batch.append(y_target[0])
        minibatch3 = random.sample(
            self.memory2, min(len(self.memory2), int(batch_size * 0.25))
        )
        for state, action, reward, next_state, done in minibatch3:
            state = state.reshape((1, 12 * 2 + 1))
            next_state = next_state.reshape((1, 12 * 2 + 1))
            y_target = self.target_model.predict(state)
            y_target[0][action] = (
                reward
                if done
                else reward
                + self.gamma * np.max(self.target_model.predict(next_state)[0])
            )
            x_batch.append(state[0])
            y_batch.append(y_target[0])
        minibatch4 = random.sample(
            self.memory3, min(len(self.memory3), int(batch_size * 0.25))
        )
        for state, action, reward, next_state, done in minibatch4:
            state = state.reshape((1, 12 * 2 + 1))
            next_state = next_state.reshape((1, 12 * 2 + 1))
            y_target = self.target_model.predict(state)
            y_target[0][action] = (
                reward
                if done
                else reward
                + self.gamma * np.max(self.target_model.predict(next_state)[0])
            )
            x_batch.append(state[0])
            y_batch.append(y_target[0])
        self.model.fit(
            np.array(x_batch), np.array(y_batch), batch_size=len(x_batch), verbose=0
        )
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        if random.random() < self.tau:
            self.target_model.set_weights(self.model.get_weights())

    def run(self):
        for e in tqdm.tqdm(range(self.n_episodes)):
            done = False
            state = self.env.reset(random.randint(0, len(self.env.notes) - 1))
            while not done:
                action = self.choose_action(state, self.get_epsilon(e))
                next_state, reward, done, _ = self.env.step(action)
                self.remember(state, action, reward, next_state, done)
                state = next_state
            self.replay(self.batch_size)
            if e % 100 == 0:
                self.model.save("checkpoint")
        return e
