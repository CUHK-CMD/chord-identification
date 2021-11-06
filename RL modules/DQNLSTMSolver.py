from collections import deque
from tensorflow.keras.models import Sequential, Model
from tensorflow.keras.layers import Dense, Input, Flatten, LSTM
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


class DQNLSTMSolver:
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
        timesteps=10,
    ):
        self.env = env
        self.memory = deque(maxlen=5000)
        self.gamma = gamma
        self.epsilon = epsilon
        self.epsilon_min = epsilon_min
        self.epsilon_decay = epsilon_log_decay
        self.alpha = alpha
        self.tau = tau
        self.alpha_decay = alpha_decay
        self.n_episodes = n_episodes
        self.batch_size = batch_size
        self.timesteps = timesteps
        if max_env_steps is not None:
            self.env._max_episode_steps = max_env_steps
        input_shape = list(self.env.observation_space.shape)
        input_shape.insert(0, self.timesteps)
        input_shape = tuple(input_shape)
        # Init model (LSTM treat as many to 1)
        state_input = Input(shape=input_shape)
        h2 = LSTM(128)(state_input)
        h3 = Dense(64, activation="ReLU")(h2)
        output = Dense(2, activation="linear")(h3)
        self.model = Model(inputs=state_input, outputs=output)
        adam = Adam(learning_rate=self.alpha)
        self.model.compile(loss=huber_loss, optimizer=adam)
        # Target model (Basically the same thing)
        state_input2 = Input(shape=input_shape)
        h22 = LSTM(128)(state_input2)
        h32 = Dense(64, activation="ReLU")(h22)
        output2 = Dense(2, activation="linear")(h32)
        self.target_model = Model(inputs=state_input2, outputs=output2)
        adam2 = Adam(learning_rate=self.alpha)
        self.target_model.compile(loss=huber_loss, optimizer=adam2)

    def remember(self, episode):
        self.memory.append(episode)

    def choose_action(self, state, epsilon):
        state = np.array(state)
        state = state.reshape((1, self.timesteps, 2 * 12 + 1))
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
        while len(x_batch) < batch_size:
            minibatch = random.sample(self.memory, 1)[0]
            ending_index = random.randint(1, len(minibatch))
            if ending_index <= self.timesteps:
                data = minibatch[:ending_index]
            else:
                data = minibatch[ending_index - self.timesteps : ending_index]
            traindata = []
            for state, action, reward, next_state, done in data:
                traindata.append(state)
            while len(traindata) < self.timesteps:
                traindata.insert(0, [0 for i in range(12 * 2 + 1)])
            state, action, reward, next_state, done = data[-1]
            traindatanp = np.array(traindata)
            traindatanp = traindatanp.reshape((1, self.timesteps, 25))
            y_target = self.target_model.predict(traindatanp)
            if not done:
                tempdata = traindata.copy()
                del tempdata[0]
                tempdata.append(next_state)
                tempdatanp = np.array(tempdata)
                tempdatanp = tempdatanp.reshape((1, self.timesteps, 25))
            y_target[0][action] = (
                reward
                if done
                else reward
                + self.gamma * np.max(self.target_model.predict(tempdatanp)[0])
            )
            x_batch.append(traindata)
            y_batch.append(y_target[0])

        history = self.model.fit(
            np.array(x_batch), np.array(y_batch), batch_size=len(x_batch), verbose=0
        )
        if self.epsilon > self.epsilon_min:
            self.epsilon *= self.epsilon_decay
        if random.random() < self.tau:
            self.target_model.set_weights(self.model.get_weights())
        return history.history["loss"]

    def run(self):
        # pbar = tqdm.tqdm(range(self.n_episodes))
        loss = []
        for e in range(self.n_episodes):
            # pbar.set_description(f"previous loss = {loss[-1] if len(loss)>0 else 0}")
            done = False
            state = self.env.reset(random.randint(0, len(self.env.notes) - 1))
            episode_data = []
            state_data = []
            for i in range(self.timesteps - 1):
                state_data.append(np.zeros((12 * 2 + 1,)))
            state_data.append(state)
            while not done:
                action = self.choose_action(state_data, self.get_epsilon(e))
                next_state, reward, done, _ = self.env.step(action)
                episode_data.append((state, action, reward, next_state, done))
                del state_data[0]
                state_data.append(next_state)
            self.remember(episode_data)
            replayloss = self.replay(self.batch_size)
            loss.append(replayloss[0])
            if e % 100 == 0:
                print(e)
                np.save("loss.npy", np.array(loss))
                self.model.save("checkpoint")
        return loss
