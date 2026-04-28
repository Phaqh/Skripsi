# %% [markdown]
# # game
# ## payoff matrix
# T,R,P,S = 3,2,1,0

# %% [markdown]
# ## Preparation

# %%
import random
import math

import os
import json
from types import SimpleNamespace
from concurrent.futures import ProcessPoolExecutor

# make sure output folder exists
os.makedirs("logs", exist_ok=True)


# %%
C, D = 0, 1

PAYOFF = [
    [(2, 2), (0, 3)],
    [(3, 0), (1, 1)]
]

class MatchState:
    def __init__(self, N=5, T=200, e = 0.01):
        self.N = N
        self.T = T
        self.e = e
        self.reset_match()
    
    def set_strategies(self, s1, s2):
        self.strategy1_name = str(s1)
        self.strategy2_name = str(s2)

    def reset_game(self):
        if self.history:
            self.all_history.append({
                "strategy1": self.strategy1_name,
                "strategy2": self.strategy2_name,
                "history": self.history.copy()
            })
        self.history = []
        self.t = 0
        self.n += 1

    def reset_match(self):
        self.history = []
        self.all_history = []
        self.t = 0
        self.n = 0

    @property
    def turn(self):
        return self.t

    def history_for_player(self, player_id):
        if player_id == 1:
            return self.history
        return [(b, a, r2, r1) for (a, b, r1, r2) in self.history]

    def _state_for_player(self, player_id):
        return SimpleNamespace(history=self.history_for_player(player_id), turn=self.turn)

    def step(self, a, b):
        # trembling hand noise (independent per player)
        if random.random() < self.e:
            a = 1 - a  # flip action of player 1

        if random.random() < self.e:
            b = 1 - b  # flip action of player 2

        r1, r2 = PAYOFF[a][b]

        self.history.append((a, b, r1, r2))
        self.t += 1

        return a,b,r1,r2

    def is_game_over(self):
        return self.t >= self.T

    def is_match_over(self):
        return self.n >= self.N
    
    def step_play(self, strategy1, strategy2):
        s1_state = self._state_for_player(1)
        s2_state = self._state_for_player(2)

        a = strategy1.act(s1_state)
        b = strategy2.act(s2_state)

        if a not in (0, 1):
            raise ValueError(f"{strategy1.__class__.__name__} returned invalid move: {a}")
        if b not in (0, 1):
            raise ValueError(f"{strategy2.__class__.__name__} returned invalid move: {b}")

        a, b, r1, r2 = self.step(a, b)

        # ✅ THIS WAS MISSING
        strategy1.remember(a, b, r1, r2)
        strategy2.remember(b, a, r2, r1)

    def game_play(self, strategy1, strategy2):
        self.reset_game()
        strategy1.reset()
        strategy2.reset()

        while not self.is_game_over():
            self.step_play(strategy1, strategy2)

        return self.history
    
    def match_play(self, strategy1, strategy2):
        self.reset_match()
        self.set_strategies(strategy1, strategy2)

        while not self.is_match_over():
            self.reset_game()
            strategy1.reset()
            strategy2.reset()

            while not self.is_game_over():
                self.step_play(strategy1, strategy2)

        if self.history:
            self.all_history.append({
                "strategy1": self.strategy1_name,
                "strategy2": self.strategy2_name,
                "history": self.history.copy()
            })

        return self.all_history


# %% [markdown]
# ## Population initiation
# 
# 

# %%
class Strategy:
    """
    Base class for IPD strategies.

    Contract:
    - act(state) must return 0 (C) or 1 (D)
    - reset() must clear internal state between matches
    """
    def __str__(self):
        return self.__class__.__name__

    COOP = 0
    DEFECT = 1

    def __init__(self, **kwargs):
        """Allow subclasses to accept additional parameters."""
        pass

    def reset(self):
        """Reset internal state before a new match."""
        pass

    def remember(self, my_action, opp_action, reward1, reward2):
        """Optional: remember the last actions for internal state."""
        pass

    def act(self, state):
        """
        Decide next action.

        Parameters:
            state:
                state.history -> list of (my_action, opp_action)
                state.turn   -> int

        Returns:
            int: 0 (COOP) or 1 (DEFECT)
        """
        raise NotImplementedError

# %% [markdown]
# ### Finite State Machine

# %%
class TitForTat(Strategy):
    def reset(self):
        self.last_opponent = self.COOP

    def remember(self, my_move, opponent_move,r1,r2):
        self.last_opponent = opponent_move

    def act(self, state):
        if not hasattr(self, "last_opponent"):
            self.reset()

        return self.last_opponent


class TitForTwoTats(Strategy):
    def reset(self):
        self.last_two = [self.COOP, self.COOP]

    def remember(self, my_move, opponent_move,r1,r2):
        self.last_two = [self.last_two[-1], opponent_move]

    def act(self, state):
        if not hasattr(self, "last_two"):
            self.reset()

        if self.last_two[0] == self.DEFECT and self.last_two[1] == self.DEFECT:
            return self.DEFECT

        return self.COOP

# %%
# state = MatchState(N=5, T=100)
# games = state.match_play(TitForTwoTats(), Pavlov())

# print(games)

# %% [markdown]
# ### Axelrods Strategies

# %%
class K59R(Strategy):
    def reset(self):
        self.tot_cop = 0
        self.tot_def = 0
        self.nice1 = 0
        self.nice2 = 0
        self.prev_move = self.COOP
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.M += 1
        if my_move == self.COOP:
            self.tot_cop += 1
            if opp_move == self.COOP:
                self.nice1 += 1
        else:
            self.tot_def += 1
            if opp_move == self.COOP:
                self.nice2 += 1
        self.prev_move = my_move

    def act(self, state):
        COOP, DEFECT = self.COOP, self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        good = (self.nice1 / self.tot_cop) if self.tot_cop > 0 else 1.0
        bad  = (self.nice2 / self.tot_def) if self.tot_def > 0 else 0.0

        C   = 6.0 * good - 8.0 * bad - 2.0
        ALT = 4.0 * good - 5.0 * bad - 1.0

        if C >= 0.0 and C >= ALT:
            return COOP
        elif C >= 0.0:
            return 1 - self.prev_move
        elif ALT >= 0.0:
            return 1 - self.prev_move
        else:
            return DEFECT


class K73R(Strategy):
    def reset(self):
        self.IAGGD = 4
        self.IDUNU = 0
        self.IDUNB = 0
        self.IPAYB = 8
        self.ITEST = 1
        self.IPOST = 0
        self.K = 0
        self.M = 0
        self.last_opp = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.K += r_self
        self.M += 1
        self.last_opp = opp_move

    def act(self, state):
        COOP, DEFECT = self.COOP, self.DEFECT

        if self.M == 0:
            self.reset()
            return self.IPOST

        J = self.last_opp
        move = self.IPOST

        if J != self.ITEST:
            return move

        if self.ITEST == 1:
            self.IDUNU += 1
        else:
            self.IDUNB += 1

        if (self.IDUNU < self.IAGGD) and (self.IDUNB < self.IPAYB):
            return move

        self.IDUNU = 0
        self.IDUNB = 0

        self.IPOST = 1 if J == 1 else 0
        move = self.IPOST

        self.ITEST = 0 if self.IPOST == 1 else 1

        if self.ITEST == 1:
            self.IAGGD = max(1, self.IAGGD - 3 + (self.K // max(1, self.M)))
        else:
            self.IPAYB = int(1.6667 * (self.IAGGD + 1))

        return move


class K74R(Strategy):
    def reset(self):
        self.ALPHA = 1.0
        self.BETA = 0.3
        self.IOLD = 0
        self.QCA = 0.0
        self.QNA = 0.0
        self.QCB = 0.0
        self.QNB = 0.0
        self.K74R_val = 0
        self.JSW = 0
        self.JS4 = 0
        self.JS11 = 0
        self.JR = 0
        self.JL = 0
        self.JT = 0
        self.JSM = 1
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.M += 1
        J = opp_move

        if self.M > 2:
            if self.IOLD == self.COOP:
                if J == self.COOP:
                    self.QCA += 1
                self.QNA += 1
                self.ALPHA = self.QCA / self.QNA if self.QNA > 0 else 1.0
                self.QCA *= 0.8
                self.QNA *= 0.8
            else:
                if J == self.COOP:
                    self.QCB += 1
                self.QNB += 1
                self.BETA = self.QCB / self.QNB if self.QNB > 0 else 0.0
                self.QCB *= 0.8
                self.QNB *= 0.8

        if self.M <= 37:
            if J == self.JL:
                self.JSM += 1
                if self.JSM >= 3:
                    self.JS4 = 1
                if self.JSM >= 11:
                    self.JS11 = 1
            else:
                self.JSW += 1
                self.JSM = 1
            self.JT += J

        self.JL = J

        if self.M == 37:
            if (self.JS4 == 1 and
                self.JS11 == 0 and
                10 < self.JT < 26 and
                self.JSW < 26):
                self.JR = 1

    def act(self, state):
        COOP, DEFECT = self.COOP, self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        if self.JR == 1:
            return DEFECT

        self.IOLD = self.K74R_val

        POLC = 6 * self.ALPHA - 8 * self.BETA - 2
        POLALT = 4 * self.ALPHA - 5 * self.BETA - 1

        if POLC == 0 and POLC >= POLALT:
            self.K74R_val = COOP
            return COOP

        if POLALT >= 0:
            self.K74R_val = 1 - self.K74R_val
            return self.K74R_val

        self.K74R_val = DEFECT
        return DEFECT


class K74RXX(Strategy):
    def reset(self):
        self.ALPHA = 1.0
        self.BETA = 0.3
        self.IOLD = 0
        self.QCA = 0.0
        self.QNA = 0.0
        self.QCB = 0.0
        self.QNB = 0.0
        self.k74dummy = 0
        self.JSW = 0
        self.JS4 = 0
        self.JS11 = 0
        self.JR = 0
        self.JL = 0
        self.JT = 0
        self.JSM = 1
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.M += 1
        J = opp_move

        if self.M > 2:
            if self.IOLD == self.COOP:
                if J == self.COOP:
                    self.QCA += 1
                self.QNA += 1
                self.ALPHA = self.QCA / self.QNA if self.QNA > 0 else 1.0
                self.QCA *= 0.8
                self.QNA *= 0.8
            else:
                if J == self.COOP:
                    self.QCB += 1
                self.QNB += 1
                self.BETA = self.QCB / self.QNB if self.QNB > 0 else 0.0
                self.QCB *= 0.8
                self.QNB *= 0.8

        if self.M <= 37:
            if J == self.JL:
                self.JSM += 1
                if self.JSM >= 3:
                    self.JS4 = 1
                if self.JSM >= 11:
                    self.JS11 = 1
            else:
                self.JSW += 1
                self.JSM = 1
            self.JT += J

        self.JL = J

        if self.M == 37:
            if (self.JS4 == 1 and
                self.JS11 == 0 and
                10 < self.JT < 26 and
                self.JSW < 26):
                self.JR = 1

    def act(self, state):
        COOP, DEFECT = self.COOP, self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        if self.JR == 1:
            self.k74dummy = DEFECT
            return DEFECT

        self.IOLD = self.k74dummy

        POLC = 6 * self.ALPHA - 8 * self.BETA - 2
        POLALT = 4 * self.ALPHA - 5 * self.BETA - 1

        if POLC == 0 and POLC >= POLALT:
            self.k74dummy = COOP
            return COOP

        if POLALT >= 0:
            self.k74dummy = 1 - self.k74dummy
            return self.k74dummy

        self.k74dummy = DEFECT
        return DEFECT


class K75R(Strategy):
    def reset(self):
        self.HIST = [[0, 0] for _ in range(4)]
        self.IBURN = 0
        self.ID = [0, 0]
        self.IDEF = 0
        self.ITWIN = 0
        self.ISTRNG = 0
        self.ICOOP = 0
        self.ITRY = 0
        self.IRDCHK = 0
        self.IRAND = 0
        self.IPARTY = 1
        self.IND = 0
        self.MY = 0
        self.INDEF = 5
        self.IOPP = 0
        self.PROB = 0.2
        self.last_J = 0
        self.last_r = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_J = opp_move
        self.last_r = r_self
        self.M += 1

    def act(self, state):
        COOP, DEFECT = self.COOP, self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        J = self.last_J

        if self.IRAND == 1:
            self.IRDCHK += J * 4 - 3
            if self.IRDCHK < 11:
                self.MY = DEFECT
                return DEFECT
            else:
                self.IRAND = 2
                self.ICOOP = 2
                self.MY = COOP
                return COOP

        self.IOPP += J
        self.HIST[self.IND][J] += 1

        if (self.M >= 15 and self.M % 15 == 0 and self.IRAND != 2):
            if self.HIST[0][0] / max(1, (self.M - 2)) < 0.8:
                if (self.IOPP * 4 >= (self.M - 2)) and (self.IOPP * 4 <= 3 * self.M - 6):

                    ROW = [sum(row) for row in self.HIST]
                    COL = [sum(self.HIST[i][j] for i in range(4)) for j in range(2)]

                    chi = 0.0
                    for i in range(4):
                        for j2 in range(2):
                            expected = ROW[i] * COL[j2] / max(1, (self.M - 2))
                            if expected > 1:
                                diff = self.HIST[i][j2] - expected
                                chi += (diff ** 2) / expected

                    if chi <= 3:
                        self.IRAND = 1
                        self.MY = DEFECT
                        return DEFECT

        if self.ITRY == 1 and J == DEFECT:
            self.IBURN = 1

        if self.M <= 37 and J == COOP:
            self.ITWIN += 1

        if self.M == 38 and J == DEFECT:
            self.ITWIN += 1

        if self.M >= 39 and self.ITWIN == 37 and J == DEFECT:
            self.ITWIN = 0

        if self.ITWIN == 37:
            return self._coop_phase()

        self.IDEF = self.IDEF * J + J
        if self.IDEF >= 20:
            return self._defect_phase()

        self.IPARTY = 3 - self.IPARTY
        idx = self.IPARTY - 1

        self.ID[idx] = self.ID[idx] * J + J
        if self.ID[idx] >= self.INDEF:
            self.ID[idx] = 0
            self.ISTRNG += 1
            if self.ISTRNG == 8:
                self.INDEF = 3

        if self.ICOOP >= 1:
            return self._coop_phase()

        if self.M >= 37 and self.IBURN == 0:
            if self.M == 37 or (self.last_r <= self.PROB):
                self.ITRY = 2
                self.ICOOP = 2
                self.PROB += 0.05
                return self._defect_phase()

        if J == COOP:
            return self._coop_phase()

        return self._defect_phase()

    def _coop_phase(self):
        self.ITRY -= 1
        self.ICOOP -= 1
        self.MY = self.COOP
        self._update_index()
        return self.COOP

    def _defect_phase(self):
        idx = self.IPARTY - 1
        self.ID[idx] += 1
        self.MY = self.DEFECT
        self._update_index()
        return self.DEFECT

    def _update_index(self):
        self.IND = 2 * self.MY + self.last_J

# %%
import random

class K92R(Strategy):
    def reset(self):
        self.last_opp = self.COOP
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

    def act(self, state):
        if self.M == 0:
            return self.COOP
        return self.last_opp


class KPavlovC(Strategy):
    def reset(self):
        self.last_my = self.COOP
        self.last_opp = self.COOP
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_my = my_move
        self.last_opp = opp_move
        self.M += 1

    def act(self, state):
        if self.M == 0:
            return self.COOP

        if self.last_opp == self.last_my:
            return self.COOP
        else:
            return self.DEFECT


class KRandomC(Strategy):
    def reset(self):
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.M += 1

    def act(self, state):
        return self.DEFECT if random.random() <= 0.5 else self.COOP


class KTF2TC(Strategy):
    def reset(self):
        self.last_opp = self.COOP
        self.prev_opp = self.COOP
        self.count = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.prev_opp = self.last_opp
        self.last_opp = opp_move
        self.count += 1

    def act(self, state):
        if self.count == 0:
            return self.COOP

        if self.count < 2:
            return self.COOP

        if self.last_opp == self.DEFECT and self.prev_opp == self.DEFECT:
            return self.DEFECT

        return self.COOP


class KTitForTatC(Strategy):
    def reset(self):
        self.last_opp = self.COOP
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

    def act(self, state):
        if self.M == 0:
            return self.COOP
        return self.last_opp

# %%
import random
import math

class GRASR(Strategy):
    def reset(self):
        self.NMOV = [0, 0, 0, 0]
        self.NMOVE = 0
        self.IGAME = 0
        self.N = 0
        self.MMOVE = 0
        self.last_opp = 0
        self.JSCOR = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.JSCOR += r_opp
        self.M += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        M = self.M + 1
        JPICK = self.last_opp
        JSCOR = self.JSCOR
        RANDO = random.random()

        if M <= 2:
            return COOP

        if M < 51:
            return JPICK

        if M == 51:
            return DEFECT

        if M < 57:
            idx = M - 53
            if 0 <= idx < 4:
                self.NMOV[idx] = self.MMOVE + JPICK

            move = JPICK

            if move == COOP:
                self.MMOVE = 2
            else:
                self.MMOVE = 4

            return move

        if M == 57:
            if JSCOR > 135:
                J = self.NMOV[1]

                if J == 1:
                    if self.NMOV[0] == 3 and self.NMOV[2] >= 3:
                        self.IGAME = 2
                        return COOP

                elif J == 2:
                    if self.NMOV[0] == 2 and self.NMOV[2] >= 4 and self.NMOV[3] >= 2:
                        self.IGAME = 4
                        return COOP

                elif J == 3:
                    if self.NMOV[0] == 5 and self.NMOV[2] >= 5:
                        self.IGAME = 2
                        return COOP

                self.IGAME = 1
                self.N = int(RANDO * 10 + 5)
                return COOP
            else:
                self.IGAME = 3
                return DEFECT

        if self.IGAME == 1:
            if self.N <= 0:
                self.N = int(RANDO * 10 + 5)
                return DEFECT
            else:
                self.N -= 1
                return JPICK

        elif self.IGAME == 2:
            return JPICK

        elif self.IGAME == 3:
            return DEFECT

        elif self.IGAME == 4:
            if M >= 118:
                self.IGAME = 2
            return COOP

        return COOP


class K31R(Strategy):
    def reset(self):
        self.S = 0.0
        self.M = 0
        self.last_opp = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.S += opp_move
        self.M += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return DEFECT

        M = self.M + 1
        A = self.S / M if M > 0 else 0

        if A < 0.5:
            return COOP
        return DEFECT


class K32R(Strategy):
    def reset(self):
        self.C1 = 0
        self.C2 = 0
        self.C3 = 0
        self.C4 = 0

        self.J2 = 0
        self.J1 = 0
        self.I2 = 0
        self.I1 = 0

        self.last_opp = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

        if self.M > 2:
            if self.I2 == self.DEFECT:
                if opp_move == self.COOP:
                    self.C1 += 1
                else:
                    self.C2 += 1
            else:
                if opp_move == self.COOP:
                    self.C3 += 1
                else:
                    self.C4 += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        J = self.last_opp
        R = random.random()
        M = self.M + 1

        if M >= 27:
            if (self.C1 >= ((self.C1 + self.C2) - 1.5 * math.sqrt(self.C1 + self.C2)) / 2 and
                self.C4 >= ((self.C3 + self.C4) - 1.5 * math.sqrt(self.C3 + self.C4)) / 2):
                move = DEFECT
                self._update_memory(J, move)
                return move

        move = COOP

        if self.J1 == J:
            if self.J2 == self.J1:
                move = J
            else:
                P = 0.9
                move = J if R < P else 1 - J
        else:
            if J == DEFECT:
                P = 0.6
            else:
                P = 0.7
            move = J if R < P else 1 - J

        self._update_memory(J, move)
        return move

    def _update_memory(self, J, move):
        self.J2 = self.J1
        self.J1 = J
        self.I2 = self.I1
        self.I1 = move

# %%
import random

class K33R(Strategy):
    def reset(self):
        self.coop_count = [0.0] * 4
        self.count = [0.0] * 4
        self.P = [0.0] * 4

        self.LAST1 = 1
        self.LAST2 = 1

        self.TWIN = True
        self.M = 0
        self.last_opp = 0

        self.CONST = [0., 4., 6., 6., 8., 12.]
        self.COEFF = [
            [36., 16., 0., 12.],
            [0., 12., 18., 12.],
            [0., 12., 24., 9.],
            [0., 0., 0., 9.],
            [12., 48., 0., 0.],
            [0., 0., 0., 0.]
        ]

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.M += 1
        self.last_opp = opp_move

        if self.M > 2:
            INDEX = 2 * self.LAST2 + self.LAST1
            self.coop_count[INDEX] += (1 - opp_move)
            self.count[INDEX] += 1
            if self.count[INDEX] > 0:
                self.P[INDEX] = self.coop_count[INDEX] / self.count[INDEX]

        if self.M > 1 and opp_move != self.LAST1:
            self.TWIN = False

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        M = self.M + 1
        INDEX = 2 * self.LAST2 + self.LAST1

        if M <= 22:
            move = COOP if INDEX in [0, 1] else DEFECT
            self._update(move)
            return int(move)

        if self.TWIN:
            move = COOP
            self._update(move)
            return int(move)

        BEST = -float("inf")
        IPOL = 0

        for i in range(6):
            SUM = self.CONST[i]
            for j in range(4):
                SUM += self.COEFF[i][j] * self.P[j]
            if SUM > BEST:
                BEST = SUM
                IPOL = i

        policy_map = {
            0: [COOP, COOP, COOP, COOP],
            1: [DEFECT, COOP, COOP, COOP],
            2: [DEFECT, COOP, DEFECT, COOP],
            3: [DEFECT, DEFECT, COOP, COOP],
            4: [DEFECT, DEFECT, DEFECT, COOP],
            5: [DEFECT, DEFECT, DEFECT, DEFECT],
        }

        policy = policy_map.get(IPOL, [COOP] * 4)
        move = int(policy[INDEX])

        self._update(move)
        return move

    def _update(self, move):
        self.LAST2 = self.LAST1
        self.LAST1 = move


class K34R(Strategy):
    def reset(self):
        self.JT = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.JT += opp_move

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if not self.JT:
            self.reset()
            return COOP

        if self.JT > 0:
            return DEFECT
        return COOP


class K35R(Strategy):
    def reset(self):
        self.FLACK = 0.0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.FLACK = (self.FLACK + opp_move) * 0.5

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if not self.FLACK:
            self.reset()
            return COOP

        R = random.random()

        if self.FLACK > R:
            return DEFECT
        return COOP


class K36R(Strategy):
    def reset(self):
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.M += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if not self.M:
            self.reset()

        M = self.M + 1
        R = random.random()

        move = DEFECT

        if 1 <= M < 100:
            PROBC = 0.1
        elif 100 <= M < 200:
            PROBC = 0.05
        elif 200 <= M < 300:
            PROBC = 0.15
        else:
            PROBC = 0.0

        if R < PROBC:
            move = COOP

        return move

# %%
import random

class K37R(Strategy):
    def reset(self):
        self.ND = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.ND += opp_move
        self.M += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if not self.ND:
            self.reset()
            return COOP

        M = self.M + 1

        if 5 * self.ND > M:
            return DEFECT
        return COOP


class K38R(Strategy):
    def reset(self):
        self.MOVE = 0
        self.JHIS = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        if self.MOVE != self.DEFECT:
            if self.JHIS >= 4:
                self.JHIS -= 4
            self.JHIS = self.JHIS * 2 + opp_move

            if self.JHIS == 7:
                self.MOVE = self.DEFECT

    def act(self, state):
        COOP = self.COOP

        if not self.JHIS:
            self.reset()
            return COOP

        return self.MOVE


class K39R(Strategy):
    def reset(self):
        self.STEP = 1
        self.SUBSTP = 1
        self.BOTHD = 0
        self.TITCNT = 0
        self.TATCNT = 0
        self.EVIL = 0
        self.N = 1
        self.F = 0
        self.OK = [0, 0, 0]
        self.TOTK = 0
        self.OLDMOV = 0
        self.VOLDMV = 0   # ✅ FIX
        self.COUNT = 0

        self.last_move = self.COOP
        self.last_opp = None   # ✅ FIX (None = no history)
        self.K = 0
        self.M = 0             # ✅ FIX (turn counter)

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.M += 1
        self.K += r_self
        self.last_opp = opp_move

        if self.last_move + opp_move == 2:
            self.BOTHD += 1
        else:
            self.BOTHD = 0

        self.COUNT -= 1

        if opp_move == self.DEFECT:
            self.TATCNT += 1
        if self.EVIL == 0 and opp_move == self.DEFECT:
            self.EVIL = 1

        self.VOLDMV = self.OLDMOV
        self.OLDMOV = opp_move

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        # ✅ ONLY reset at first move
        if self.M == 0:
            self.reset()
            return COOP

        J = self.last_opp
        K = self.K

        move = COOP

        while True:
            if self.STEP == 1:
                if self.SUBSTP == 1:
                    self.COUNT = 10
                    self.TATCNT = 0
                    self.TITCNT = 0
                    self.SUBSTP = 2
                    continue

                elif self.SUBSTP == 2:
                    if (self.VOLDMV + self.OLDMOV) == 2:
                        move = DEFECT
                    else:
                        move = COOP

                    self.TITCNT += move

                    if self.COUNT == 0:
                        self.SUBSTP = 3
                    break

                elif self.SUBSTP == 3:
                    OLDSTP = self.STEP
                    self.OK[self.STEP - 1] = K - self.TOTK
                    self.TOTK = K
                    self.SUBSTP = 1

                    if self.TATCNT == 0:
                        self.STEP = 4
                        if self.EVIL == 1:
                            self.STEP = 1
                        if self.EVIL == 0:
                            self.EVIL = -1
                        continue

                    self.STEP = 1
                    for i1 in range(2):
                        for i2 in range(1, 3):
                            if self.OK[i1] == 0 or self.OK[i2] == 0:
                                continue
                            if self.OK[i1] < self.OK[i2]:
                                if self.STEP == i1 + 1:
                                    self.STEP = i2 + 1

                    if self.STEP != 3:
                        if (self.OK[min(self.STEP, 2)] == 0 and
                            (self.TATCNT >= 4 or self.TITCNT == 0)):
                            self.STEP += 1

                    if self.STEP < OLDSTP and self.BOTHD > 0:
                        self.STEP = 5

                    continue

            elif self.STEP == 2:
                if self.SUBSTP == 1:
                    self.COUNT = 10
                    self.SUBSTP = 2
                    continue

                elif self.SUBSTP == 2:
                    move = DEFECT if self.OLDMOV == DEFECT else COOP
                    self.TITCNT += move
                    if self.COUNT == 0:
                        self.SUBSTP = 3
                    break

                elif self.SUBSTP == 3:
                    self.SUBSTP = 1
                    self.STEP = 1
                    continue

            elif self.STEP == 3:
                if self.SUBSTP == 1:
                    self.COUNT = 10
                    self.SUBSTP = 2
                    continue

                elif self.SUBSTP == 2:
                    move = DEFECT
                    self.TITCNT += 1
                    if self.COUNT == 0:
                        self.SUBSTP = 3
                    break

                elif self.SUBSTP == 3:
                    self.SUBSTP = 1
                    self.STEP = 1
                    continue

            elif self.STEP == 4:
                if self.SUBSTP == 1:
                    self.SUBSTP = 2
                    move = DEFECT
                    self.COUNT = self.N
                    self.TATCNT = 0
                    break

                elif self.SUBSTP == 2:
                    if self.COUNT == 0:
                        self.SUBSTP = 3
                    break

                elif self.SUBSTP == 3:
                    if self.TATCNT == 0:
                        self.F = 1
                        self.SUBSTP = 1
                        continue
                    else:
                        if self.F == 1:
                            self.N += 1
                            self.SUBSTP = 1
                            self.STEP = 1
                            continue
                        else:
                            self.SUBSTP = 4
                            if J == DEFECT:
                                self.N += 1
                            self.TATCNT = J
                            break

                elif self.SUBSTP == 4:
                    if self.TATCNT > 4:
                        self.SUBSTP = 1
                        self.STEP = 1
                        continue
                    break

            elif self.STEP == 5:
                if self.SUBSTP != 2:
                    self.COUNT = 5
                    self.SUBSTP = 2

                if self.COUNT != 0:
                    break
                else:
                    self.SUBSTP = 1
                    self.STEP = 1
                    continue

            break

        self.last_move = move
        return move


class K40R(Strategy):
    def reset(self):
        self.S = 3
        self.W = 0
        self.Q = 0.8
        self.M = 0
        self.last_opp = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.M += 1
        self.last_opp = opp_move

        self.S += 1

        if opp_move == self.DEFECT:
            self.W += 1
            self.Q *= 0.5

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        M = self.M + 1
        J = self.last_opp
        R = random.random()

        if M < 3:
            return COOP

        if J == DEFECT:
            self.W += 1

            cond1 = (self.W > 2 and (self.W % 3 == 0))
            cond2 = ((self.W - 1) % 3 == 0)

            if cond1 or cond2:
                self.S = 1
                self.Q *= 0.5
            else:
                if R < self.Q:
                    self.Q *= 0.5
                    return COOP
                else:
                    self.Q *= 0.5
                    return DEFECT

        if self.S in [1, 2]:
            return DEFECT

        cond1 = (self.W > 2 and (self.W % 3 == 0))
        cond2 = ((self.W - 1) % 3 == 0)

        if cond1 or cond2:
            self.S = 1
            self.Q *= 0.5
            return DEFECT

        return COOP

# %%
class K41R(Strategy):
    def reset(self):
        self.LAST = [0] * 12
        self.ICASE = 1
        self.IFORGV = 0
        self.last_opp = self.COOP
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

    def act(self, state):
        COOP = self.COOP

        if self.M == 0:
            self.reset()
            return COOP

        J = self.last_opp
        M = self.M + 1

        if self.ICASE == 1:
            move = J
            self.ICASE = J + 1

        elif self.ICASE == 2:
            move = J
            self.ICASE = 3
            if J == 1:
                self.ICASE = 1

        elif self.ICASE == 3:
            move = J
            if self.IFORGV < M:
                move = 0
            self.IFORGV += 20 * J
            self.ICASE = 1

        LSUM = self.LAST[0]
        for i in range(1, 12):
            LSUM += self.LAST[i]
            self.LAST[i - 1] = self.LAST[i]

        self.LAST[11] = J

        if LSUM >= 5:
            move = 1

        return move


class K42R(Strategy):
    def reset(self):
        self.MHIST = [[0, 0], [0, 0]]
        self.L3MOV = 0
        self.L3ECH = 0
        self.IDEF = 0
        self.ICOOP = 0
        self.IPICK = 0
        self.I2PCK = 0
        self.J2PCK = 0
        self.last_opp = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

        if self.M != 1:
            self.MHIST[self.I2PCK][opp_move] += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        JPICK = self.last_opp
        MOVEN = self.M + 1

        if self.IDEF != 0:
            move = DEFECT
        else:
            if self.IPICK == 1 and JPICK == 1:
                self.L3MOV += 1
                if self.L3MOV >= 3:
                    move = COOP
                    self.L3MOV = 0
                    self.L3ECH = 0
                else:
                    move = JPICK
            else:
                self.L3MOV = 0

                if (
                    self.IPICK != JPICK and
                    JPICK == self.I2PCK and
                    self.IPICK == self.J2PCK
                ):
                    self.L3ECH += 1
                    if self.L3ECH >= 3:
                        self.L3ECH = 0
                        self.L3MOV = 0
                        self.ICOOP = 1
                else:
                    self.L3ECH = 0

                move = JPICK

        if (MOVEN - 2) % 25 == 0 and MOVEN != 2:
            self.IDEF = 0
            JNCOP = self.MHIST[0][0] + self.MHIST[1][0]

            if JNCOP < 8:
                if JNCOP < 3:
                    self.IDEF = 1
            else:
                if 100 * self.MHIST[0][0] / max(JNCOP, 1) < 70:
                    self.IDEF = 1

            self.MHIST = [[0, 0], [0, 0]]

            if self.IDEF != 0:
                self.ICOOP = 0
                self.L3MOV = 0
                self.L3ECH = 0
                move = DEFECT

        if self.ICOOP != 0 and move == DEFECT:
            self.ICOOP = 0
            move = COOP

        self.I2PCK = self.IPICK
        self.J2PCK = JPICK
        self.IPICK = move

        return move


class K43R(Strategy):
    def reset(self):
        self.NCC = 0
        self.NCD = 0
        self.NDC = 0
        self.NDD = 0
        self.KOUNT = 0
        self.MYTWIN = 0
        self.IOLD1 = 0
        self.IOLD2 = 0
        self.last_opp = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

        if self.M >= 3:
            if self.IOLD2 == 1:
                self.NDC += (1 - opp_move)
                self.NDD += opp_move
            else:
                self.NCC += (1 - opp_move)
                self.NCD += opp_move

    def act(self, state):
        COOP = self.COOP

        if self.M == 0:
            self.reset()
            return 0

        J = self.last_opp
        M = self.M + 1

        self.IOLD2 = self.IOLD1

        if M < 16:
            if J == 0 or self.KOUNT >= 3:
                self.IOLD1 = 0
                return 0
            self.KOUNT += 1
            self.IOLD1 = 1
            return 1

        if M == 17 and J == 1 and self.NCD == 1 and self.NDD == 0:
            self.MYTWIN = 1

        if (self.NCD * 3) >= (self.NCC + self.NCD):
            self.IOLD1 = 1
            return 1

        if M % 4 != 0:
            self.IOLD1 = 0
            return 0

        if self.MYTWIN == 1:
            self.IOLD1 = 0
            return 0

        if self.NDC >= (M // 12) or self.NDD == 0:
            self.IOLD1 = 1
            return 1

        self.IOLD1 = 0
        return 0


class K44R(Strategy):
    def reset(self):
        self.MC = 0
        self.F = 2
        self.AM = 4
        self.last_opp = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1
        self.MC += opp_move

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        M = self.M + 1
        R = random.random()

        if M < 3:
            return COOP

        if self.MC < self.AM:
            return COOP

        if self.MC == self.AM:
            return DEFECT

        self.AM = self.AM / self.F
        self.MC = 0

        if R < self.AM:
            return COOP

        return DEFECT


class K45R(Strategy):
    def reset(self):
        self.JOLD = 0
        self.A = 0
        self.B = 0
        self.C = 0
        self.D = 0
        self.E = 0
        self.last_opp = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return DEFECT

        J = self.last_opp
        M = self.M + 1

        if M <= 3:
            if M == 2:
                self.D = 1 if J == 1 else 0
                return COOP

            if M == 3:
                if J == 1:
                    if self.D == 1:
                        self.C = 1
                    return COOP
                else:
                    if self.D == 1:
                        return COOP
                    self.A = 1
                    return COOP

        if self.C == 1:
            return J

        if self.B == 1:
            move = COOP
            if self.JOLD == 1 and J == 1:
                move = DEFECT
            self.JOLD = J
            return move

        if self.A == 1:
            move = DEFECT
            self.E += 1
            if self.E == 8:
                self.E = 0
                self.JOLD = J
                return move
            if not (self.JOLD == 1 and J == 1):
                move = COOP
            self.JOLD = J
            return move

        if self.D == 1:
            if J == 1:
                self.C = 1
                return DEFECT
            else:
                self.B = 1
                return COOP

        if J == 1:
            self.C = 1
            return COOP
        else:
            self.B = 1
            return COOP

# %%
import random

class K46R(Strategy):
    def reset(self):
        self.NJ = 0
        self.last_opp = None
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1
        self.NJ += opp_move

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            return COOP

        J = self.last_opp
        R = random.random()

        if J == COOP:
            return COOP

        P = self.NJ / self.M if self.M > 0 else 0.0

        return DEFECT if R < P else COOP


class K47R(Strategy):
    def reset(self):
        self.NUM = 2
        self.DEN = 2
        self.RF = 20
        self.LONG = 1
        self.SHORT = 5
        self.SH2 = [1] * 5
        self.N = 1
        self.MYLAST = 0
        self.MYMOVE = 0
        self.last_opp = None
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

        J = opp_move

        if self.M <= self.RF and J == self.DEFECT:
            self.RF = self.M + (20 * self.NUM) // self.DEN + 1

        self.N = (self.N % 4) + 1
        self.SHORT -= self.SH2[self.N - 1]

        if J == self.MYLAST:
            self.LONG += 1
            self.SHORT += 1
            self.SH2[self.N - 1] = 1
        else:
            self.SH2[self.N - 1] = 0

        self.MYLAST = self.MYMOVE

        if self.M >= self.RF + 2:
            self.NUM += J
            self.DEN += (1 - J)
            if self.DEN != 0:
                self.RF = self.M + (20 * self.NUM) // self.DEN + 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            return COOP

        J = self.last_opp
        M = self.M + 1

        move = J

        if (self.LONG < 0.625 * M) or (self.SHORT < 3):
            move = DEFECT

        if (self.LONG > 0.9 * M) and (self.SHORT == 5):
            move = COOP

        if M == self.RF:
            move = DEFECT

        if M >= self.RF + 2:
            move = COOP

        self.MYMOVE = move
        return move


class K48R(Strategy):
    def reset(self):
        self.IARRAY = [0] * 5
        self.IPO2 = [2, 4, 3, 5, 1]
        self.K5 = 0
        self.KLAST = 0
        self.MM = 0
        self.ICHAN = 1
        self.IPO1 = 1
        self.last_opp = None
        self.M = 0
        self.score = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1
        self.score += r_self

    def act(self, state):
        if self.M == 0:
            return self.COOP

        J = self.last_opp
        M = self.M + 1
        K = self.score

        if M <= 5:
            idx = self.IPO2[self.IPO1 - 1] - 1
            self.IARRAY[idx] = J
            self.IPO1 += J
            return J

        self.MM = ((M - 1) % 5) + 1
        move = self.IARRAY[self.MM - 1]

        if self.MM != 1:
            return move

        KOLD = self.K5
        self.K5 = K - self.KLAST
        self.KLAST = K

        if KOLD > self.K5:
            self.ICHAN = -self.ICHAN
            self.IPO1 += self.ICHAN

        self.IPO1 = max(1, min(5, self.IPO1))

        idx = self.IPO2[self.IPO1 - 1] - 1
        self.IARRAY[idx] += self.ICHAN
        self.IPO1 += self.ICHAN

        move = self.IARRAY[self.MM - 1]

        if move >= 1:
            return self.DEFECT
        else:
            return self.COOP


class K49R(Strategy):
    def reset(self):
        self.JDSUM = 0
        self.last_opp = None
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1
        if opp_move == self.DEFECT:
            self.JDSUM += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            return COOP

        J = self.last_opp
        M = self.M + 1
        R = random.random()

        JDPC = (100 * self.JDSUM) // self.M

        if J == COOP:
            move = COOP
        elif self.JDSUM <= 17:
            move = int(R + 0.5)
        else:
            move = DEFECT

        if (M > 19 and JDPC > 79) or \
           (M > 29 and JDPC > 65) or \
           (M > 39 and JDPC > 39):
            move = DEFECT

        return move


class K50R(Strategy):
    def reset(self):
        self.last_opp = None
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            return COOP

        J = self.last_opp
        R = random.random()

        if J == COOP:
            return DEFECT if R >= 0.9 else COOP

        return COOP

# %%
class K51R(Strategy):
    def reset(self):
        self.LASTI = 0
        self.last_opp = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        J = self.last_opp
        M = self.M + 1

        if M <= 8:
            move = COOP
            if M == 6:
                move = DEFECT
            self.LASTI = 0
            return move

        move = COOP
        self.LASTI -= 1

        if self.LASTI == 3:
            move = DEFECT

        if self.LASTI > 0:
            return move

        if J == 1:
            move = DEFECT
            self.LASTI = 4

        return move


class K52R(Strategy):
    def reset(self):
        self.D8 = 0
        self.D9 = 0
        self.last_opp = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

        if opp_move <= 0:
            self.D9 = 0
        else:
            self.D9 += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        R = random.random()

        move = COOP

        if self.D9 >= 2:
            move = DEFECT
            if self.D9 >= (5 + 3 * self.D8):
                self.D9 = 0
                self.D8 += 1

        if R <= 0.05:
            move = 1 - move

        return move


class K53R(Strategy):
    def reset(self):
        self.C = [0] * 10
        self.M = 0
        self.last_opp = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        if self.M < 10:
            self.C[self.M] = opp_move
        else:
            self.C = self.C[1:] + [opp_move]
        self.M += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if not hasattr(self, 'last_opp') or self.M == 0:
            self.reset()
            return COOP

        R = random.random()

        if self.M <= 10:
            return COOP

        D = sum(1 for x in self.C if x == 1)

        if D > 8:
            return DEFECT if R < 0.94 else COOP
        if D == 8:
            return DEFECT if R < 0.915 else COOP
        if D in [7, 6, 5]:
            return DEFECT if R < 0.87 else COOP
        if D in [4, 3]:
            return DEFECT if R < 0.915 else COOP
        if D == 2:
            return DEFECT if R < 0.87 else COOP
        if D == 1:
            return DEFECT if R < 0.23 else COOP

        return COOP


class K54R(Strategy):
    def reset(self):
        self.OPDEF = 0
        self.STDEF = 0
        self.DL = 0.20
        self.COOPS = 0
        self.OKDEF = True
        self.MYDEF = False
        self.NODEF = 0
        self.ND = 12
        self.last_opp = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

        if opp_move == 0:
            self.STDEF = 0
            self.COOPS += 1
        else:
            self.COOPS = 0
            self.STDEF += 1
            self.OPDEF += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        J = self.last_opp
        M = self.M + 1

        if M == 20:
            self.DL = 0.10

        if J == 0:
            if float(self.OPDEF) <= float(M) * self.DL and (M % self.ND == 0) and self.OKDEF:
                self.MYDEF = False
                self.NODEF += 1
                if self.NODEF % 6 == 0:
                    self.ND -= 1
                if self.ND < 1:
                    self.ND = 1
                return DEFECT

            self.MYDEF = False
            return COOP

        if M <= 4:
            return DEFECT

        if self.MYDEF:
            self.OKDEF = False

        if float(self.OPDEF) > float(M) * self.DL or self.STDEF > 2:
            if 20 * self.OPDEF <= self.COOPS * M:
                return COOP
            return DEFECT

        self.MYDEF = False
        return COOP


class K55R(Strategy):
    def reset(self):
        self.ALPHA = 1.0
        self.BETA = 0.0
        self.IOLD = 0
        self.QCA = 0
        self.QNA = 0
        self.QCB = 0
        self.QNB = 0
        self.MUTDEF = 0
        self.last_move = 0
        self.last_opp = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

        if self.M > 2:
            if self.IOLD == 1:
                if opp_move == 0:
                    self.QCB += 1
                self.QNB += 1
                if self.QNB > 0:
                    self.BETA = self.QCB / self.QNB
            else:
                if opp_move == 0:
                    self.QCA += 1
                self.QNA += 1
                if self.QNA > 0:
                    self.ALPHA = self.QCA / self.QNA

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        J = self.last_opp

        POLC = 6 * self.ALPHA - 9 * self.BETA - 2
        POLALT = 4 * self.ALPHA - 6 * self.BETA - 1

        if POLC >= 0 and POLC >= POLALT:
            move = COOP

        elif POLC < 0 and POLALT < 0:
            move = DEFECT

            if J == 1 and self.IOLD == 1:
                self.MUTDEF += 1
                if self.MUTDEF > 3:
                    move = COOP
            else:
                self.MUTDEF = 0

        else:
            move = 1 - self.last_move

        self.IOLD = move
        self.last_move = move

        return move

# %%
class K56R(Strategy):
    def reset(self):
        self.GOOD = 1.0
        self.BAD = 0.0
        self.PAST = 0
        self.TOTCOP = 0
        self.TOTDEF = 0
        self.NICE1 = 0
        self.NICE2 = 0
        self.last_move = 0
        self.last_opp = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

        if self.M > 2:
            if self.PAST == self.DEFECT:
                if opp_move == self.COOP:
                    self.NICE2 += 1
                self.TOTDEF += 1
                if self.TOTDEF > 0:
                    self.BAD = self.NICE2 / self.TOTDEF
            else:
                if opp_move == self.COOP:
                    self.NICE1 += 1
                self.TOTCOP += 1
                if self.TOTCOP > 0:
                    self.GOOD = self.NICE1 / self.TOTCOP

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        C = 6.0 * self.GOOD - 8.0 * self.BAD - 2.0
        ALT = 4.0 * self.GOOD - 5.0 * self.BAD - 1.0

        if C >= 0.0 and C >= ALT:
            move = COOP
        elif C >= 0.0 and C < ALT:
            move = 1 - self.last_move
        elif ALT >= 0.0:
            move = 1 - self.last_move
        else:
            move = DEFECT

        self.PAST = move
        self.last_move = move

        return move


class K57R(Strategy):
    def reset(self):
        self.n = 0
        self.last_move = 0
        self.last_opp = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1
        self.n = 4 * (self.n % 16) + 2 * self.last_move + opp_move

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            self.last_move = COOP
            return COOP

        J = self.last_opp
        M = self.M + 1

        if M <= 3:
            move = J
            if M == 3 and self.n == 6:
                move = DEFECT
            self.last_move = move
            return move

        n = self.n
        move = DEFECT

        if n < 39:
            if n <= 0:
                move = COOP
            elif n < 28:
                if n == 27:
                    move = DEFECT
                else:
                    move = COOP
            elif n == 28:
                move = COOP
            elif n < 32:
                move = DEFECT
            else:
                move = COOP

        elif n == 39:
            move = DEFECT

        else:
            if n < 45:
                move = COOP
            elif n == 45:
                move = DEFECT
            elif n < 49:
                move = COOP
            elif n == 49:
                move = DEFECT
            elif n < 58:
                move = COOP
            elif n == 58:
                move = DEFECT
            elif n < 61:
                move = COOP
            elif n == 61:
                move = DEFECT
            else:
                move = COOP

        self.last_move = move
        return move


class K58R(Strategy):
    def reset(self):
        self.KAM = 0
        self.NPHA = 0
        self.last_opp = 0
        self.M = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            self.reset()
            return COOP

        M = self.M + 1
        K = getattr(state, "score", 0)

        if self.KAM > 6:
            return DEFECT

        if self.NPHA >= 1:
            self.NPHA -= 1
            if self.NPHA == 0:
                return DEFECT
            return COOP

        if (M % 18 == 0) and self.KAM > 2:
            self.KAM -= 1

        if M % 6 != 0:
            return COOP

        if K < M:
            self.KAM += 2
        if K * 10 < M * 15:
            self.KAM += 1
        if K < M * 2:
            self.KAM += 1
        if K * 10 < M * 25:
            self.KAM += 1

        self.NPHA = 2
        return DEFECT


class K60R(Strategy):
    def reset(self):
        self.ID = 0
        self.last_opp = None
        self.M = 0
        self.score = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.last_opp = opp_move
        self.M += 1
        self.score += r_self

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        if self.M == 0:
            return COOP

        J = self.last_opp
        M = self.M + 1
        K = self.score

        if self.ID != 1:
            move = J

            if (M == 11 and K < 23) or \
               (M == 21 and K < 53) or \
               (M == 31 and K < 83) or \
               (M == 41 and K < 113) or \
               (M == 51 and K < 143) or \
               (M == 101 and K < 293):
                self.ID = 1

            return move

        return DEFECT

# %%
class K61R(Strategy):
    def reset(self):
        self.ICOOP = 0
        self.turn = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1
        if opp_move == 0:
            self.ICOOP += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        ITURN = self.turn + 1

        if ITURN == 1:
            self.reset()
            return COOP

        if ITURN <= 10:
            return COOP

        ISPICK = getattr(self, "last_opp", 0)
        K61R = ISPICK

        if ITURN <= 25:
            return K61R

        COPRAT = self.ICOOP / ITURN if ITURN > 0 else 0.0
        R = random.random()

        if ISPICK == 1 and COPRAT < 0.6 and R > COPRAT:
            K61R = DEFECT
        else:
            K61R = COOP

        return K61R


class K62R(Strategy):
    def reset(self):
        self.JOLD = 0
        self.IRAN = 1
        self.turn = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1
        self.JOLD = getattr(self, "last_opp", 0)
        self.last_opp = opp_move

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        M = self.turn + 1
        R = random.random()

        if M == 1:
            self.reset()
            self.IRAN = int(23 * R) + 1
            return COOP

        K62R = COOP

        if M == self.IRAN:
            K62R = DEFECT
            self.IRAN = int(23 * R) + M + 1
        else:
            if self.JOLD == 1 and getattr(self, "last_opp", 0) == 1:
                K62R = DEFECT

        return K62R


class K63R(Strategy):
    def reset(self):
        self.ik = 1

    def remember(self, my_move, opp_move, r_self, r_opp):
        pass

    def act(self, state):
        if not hasattr(self, "ik"):
            self.reset()
        self.ik = 1 - self.ik
        return self.ik


class K64R(Strategy):
    def reset(self):
        self.A = [[0, 0], [0, 0]]
        self.E = 0
        self.F = 0
        self.X = 1
        self.Y = 1
        self.turn = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1

        if opp_move == 0:
            self.A[self.X - 1][self.Y - 1] += 1
            self.E += 1
        else:
            self.A[self.X - 1][self.Y - 1] -= 1
            self.F += 1

        self.X = opp_move + 1
        self.Y = my_move + 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        M = self.turn + 1

        if M == 1:
            self.reset()
            return COOP

        if self.A[self.X - 1][self.Y - 1] >= 0:
            K64R = COOP
        else:
            K64R = DEFECT

        P = abs(self.E - self.F)

        if M > 40 and (10 * P < M):
            K64R = DEFECT

        return K64R


class K65R(Strategy):
    def reset(self):
        self.LASTD = 0
        self.DIFF = 0
        self.TOTD = 0
        self.turn = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1

        if opp_move == 1:
            self.TOTD += 1

            if self.LASTD != 0:
                self.DIFF = self.turn - self.LASTD
                if self.DIFF <= 4:
                    self.TOTD = 10

            self.LASTD = self.turn

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        M = self.turn + 1

        if M == 1:
            self.reset()
            return COOP

        if self.TOTD >= 10:
            return DEFECT

        last_opp = getattr(self, "last_opp", 0)

        if last_opp == 0:
            return COOP

        return COOP

# %%
class K66R(Strategy):
    def reset(self):
        self.D = 0
        self.J2 = -3
        self.turn = 0
        self.last_opp = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1
        self.last_opp = opp_move
        self.D += opp_move
        self.J2 = self.J2 - 1 + 3 * opp_move
        self.J2 = max(-5, min(10, self.J2))

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        M = self.turn + 1

        if M == 1:
            self.reset()
            return COOP

        RR = self.D / M if M > 0 else 0.0

        if M < 3:
            return COOP

        if self.J2 < 3:
            return COOP

        if M <= 10:
            self.J2 = -1
            return DEFECT

        if RR < 0.15:
            return COOP

        return DEFECT


class K67R(Strategy):
    def reset(self):
        self.S = 0
        self.AD = 5
        self.NO = 0.0
        self.NK = 1.0
        self.AK = 1.0
        self.FD = 0
        self.C = 0
        self.turn = 0
        self.last_move = 0
        self.last_opp = 0
        self.K = 0
        self.L = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1
        self.last_opp = opp_move
        self.K += r_self
        self.L += r_opp

        if self.FD == 2:
            self.FD = 0
            self.NO = (self.NO * self.NK + 3 - 3 * opp_move + 2 * self.last_move - self.last_move * opp_move) / (self.NK + 1)
            self.NK += 1

        if self.FD == 1:
            self.FD = 2
            self.AD = (self.AD * self.AK + 3 - 3 * opp_move + 2 * self.last_move - self.last_move * opp_move) / (self.AK + 1)
            self.AK += 1

        if opp_move == 1:
            self.S += 1
        else:
            self.S = 0
            self.C += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        M = self.turn + 1
        R = random.random()

        if M == 1:
            self.reset()
            return COOP

        if abs(self.FD - 1.5) == 0.5:
            self.last_move = COOP
            return COOP

        if self.K >= 2.25 * M:
            P = 0.95 - (self.AD + self.NO - 5) / 15 + 1.0 / (M ** 2) - self.last_opp / 4.0
            if R > P:
                self.last_move = DEFECT
                self.FD = 1
                return DEFECT
            self.last_move = COOP
            return COOP

        if self.K >= 1.75 * M:
            P = 0.25 + self.C / M - self.S * 0.25 + (self.K - self.L) / 100.0 + 4.0 / M
            if R > P:
                self.last_move = DEFECT
                return DEFECT
            self.last_move = COOP
            return COOP

        self.last_move = self.last_opp
        return self.last_move


class K68R(Strategy):
    def reset(self):
        self.J1 = 0
        self.J2 = 0
        self.turn = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1
        self.J2 = self.J1
        self.J1 = opp_move

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT
        R = random.random()

        M = self.turn + 1

        if M == 1:
            self.reset()
            return COOP

        J = self.J1

        if self.J1 * J == 1:
            return COOP if R < 0.75 else DEFECT

        if (self.J2 * 2 + self.J1 + J * 2 + J) == 1:
            return DEFECT

        if (self.J2 * 2 + self.J1 * 2 + J) == 1:
            return COOP if R < 0.5 else DEFECT

        return DEFECT


class K69R(Strategy):
    def reset(self):
        self.S = 1
        self.F = 0
        self.D = 0
        self.C = 0
        self.turn = 0
        self.last_opp = None

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1
        self.last_opp = opp_move

        # IF (J .NE. 1) C = C + 1
        if opp_move == self.COOP:
            self.C += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT
        R = random.random()

        # IF (M == 1)
        if self.turn == 0:
            self.reset()
            return COOP

        M = self.turn + 1
        J = self.last_opp

        while True:

            # ----------------------
            # STATE 1
            # ----------------------
            if self.S == 1:

                if R < 0.1:
                    self.S = 5
                    return DEFECT  # corresponds to label 720

                if J == DEFECT:
                    self.D += 1
                else:
                    self.D = 0

                if self.D > 20:
                    self.S = 3
                    self.D = 0
                    return COOP  # 820

                if self.C >= 0.7 * (M - 3):
                    return J  # mimic

                self.S = 2
                continue  # go to state 2 (like GOTO 800)

            # ----------------------
            # STATE 2
            # ----------------------
            elif self.S == 2:

                if J == DEFECT:
                    self.D += 1
                else:
                    self.D = 0

                if self.D > 10:
                    self.S = 3
                    return DEFECT  # 830

                return DEFECT

            # ----------------------
            # STATE 3
            # ----------------------
            elif self.S == 3:

                if J == DEFECT:
                    self.D += 1
                else:
                    self.D = 0

                if self.D > 20:
                    self.S = 3
                    self.D = 0
                    return COOP  # 820

                return J

            # ----------------------
            # STATE 4
            # ----------------------
            elif self.S == 4:

                if J == DEFECT:
                    self.F += 1
                    if self.F > 3:
                        self.S = 3
                        return COOP  # 820

                # label 1006
                self.S = 1
                return COOP

            # ----------------------
            # STATE 5
            # ----------------------
            elif self.S == 5:
                # 1100: S=4 then GOTO 702 (STATE 1 continuation)
                self.S = 4
                continue  # 🔥 THIS is the critical fix

            return COOP

class K70R(Strategy):
    def reset(self):
        self.JZ = 0
        self.turn = 0
        self.last_opp = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1
        self.last_opp = opp_move

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT
        R = random.random()

        M = self.turn + 1
        J = self.last_opp

        if M == 1:
            self.reset()
            return COOP

        if self.JZ == J:
            K70R = self.JZ
        else:
            K70R = COOP
            if R > 0.2:
                K70R = DEFECT

        self.JZ = K70R
        return K70R

# %%
class K71R(Strategy):
    def reset(self):
        self.IA = 0
        self.IB = 0
        self.turn = 0
        self.last_opp = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1
        self.last_opp = opp_move

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        M = self.turn + 1
        J = self.last_opp

        if M == 1:
            self.reset()
            return COOP

        if M == 2:
            return DEFECT if J == 1 else COOP

        if J == 1:
            self.IB += 1
            if self.IB == 2:
                self.IB = 0
                return DEFECT
            return COOP

        self.IA += 1
        if self.IA == 2:
            self.IA = 0
            return DEFECT

        return COOP


class K72R(Strategy):
    def reset(self):
        self.JOLD = 0
        self.JCOUNT = 0
        self.turn = 0
        self.last_opp = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1
        self.last_opp = opp_move

        if opp_move == 1:
            self.JCOUNT += 1

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        M = self.turn + 1
        J = self.last_opp
        R = random.random()

        if M == 1:
            self.reset()
            return COOP

        N = 1.0
        if J == 1 and M > 10:
            N = math.log(M)

        if R <= ((N * self.JCOUNT) / M):
            return DEFECT

        return COOP

# %%
class K76R(Strategy):
    def reset(self):
        self.PATSY = True
        self.DC = 0
        self.MDC = 0
        self.G = 1
        self.turn = 0
        self.last_opp = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1
        self.last_opp = opp_move

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        M = self.turn + 1
        J = self.last_opp

        if M == 1:
            self.reset()
            return DEFECT

        if not self.PATSY:
            return J

        if J != 1:
            self.DC += 1
            if self.G == 0:
                self.MDC += 1

            self.G = 0
            if self.MDC / (self.DC + 1) >= 0.5:
                self.G = 1

            return self.G

        self.PATSY = False
        return COOP


class K77R(Strategy):
    def reset(self):
        self.KEXP = [100, 100, 100, 100, 100]
        self.JSTR = 3
        self.KTRY = 0
        self.KI = 0
        self.turn = 0
        self.score = 0
        self.last_opp = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1
        self.last_opp = opp_move
        self.score += r_self

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT
        RANDOM = random.random()

        MOVEN = self.turn + 1
        JPICK = self.last_opp
        ISCORE = self.score

        if MOVEN == 1:
            self.reset()

        if self.KTRY >= 20:
            self.KEXP[self.JSTR - 1] = ISCORE - self.KI

            if self.JSTR != 5:
                if self.KEXP[self.JSTR] > self.KEXP[self.JSTR - 1]:
                    self.JSTR += 1
                    JPICK = 0

            if self.JSTR == 5 or self.JSTR > 1:
                if self.KEXP[self.JSTR - 2] > self.KEXP[self.JSTR - 1]:
                    self.JSTR -= 1
                    JPICK = 0

            self.KI = ISCORE
            self.KTRY = 0

        self.KTRY += 1

        if self.JSTR == 1:
            return COOP

        if self.JSTR == 2:
            if JPICK == 0:
                return COOP
            return COOP if RANDOM <= 0.75 else DEFECT

        if self.JSTR == 3:
            return JPICK

        if self.JSTR == 4:
            if JPICK == 1:
                return DEFECT
            return COOP if RANDOM <= 0.75 else DEFECT

        return DEFECT

class K78R(Strategy):
    def reset(self):
        self.inner = GRASR()
        self.inner.reset()  # 🔥 important!

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.inner.remember(my_move, opp_move, r_self, r_opp)

    def act(self, state):
        return self.inner.act(state)  # ✅ correct delegation


class K79R(Strategy):
    def reset(self):
        self.JBACK = [0, 0, 0, 0, 0]
        self.turn = 0
        self.last_opp = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1
        self.last_opp = opp_move
        self.JBACK = self.JBACK[1:] + [opp_move]

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        M = self.turn + 1

        if M == 1:
            self.reset()
            return COOP

        if M < 6:
            return COOP

        if not self.JBACK:  # ADD THIS CHECK
            return COOP

        I1 = sum(self.JBACK)

        if I1 >= 3:
            return DEFECT
        return COOP


class K80R(Strategy):
    def reset(self):
        self.MODE = 0
        self.INOD = 0
        self.INOC = 0
        self.turn = 0
        self.last_opp = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.turn += 1
        self.last_opp = opp_move

        if opp_move == 1:
            self.INOD += 1
        else:
            self.INOC = self.turn - self.INOD

    def act(self, state):
        COOP = self.COOP
        DEFECT = self.DEFECT

        M = self.turn + 1
        J = self.last_opp

        if M == 1:
            self.reset()
            return COOP

        if self.MODE == 1:
            return DEFECT

        INOC = M - self.INOD

        T1 = 1.6667 ** self.INOD
        T2 = 0.882 ** INOC
        TEST = T1 * T2

        if TEST >= 5.0:
            self.MODE = 1
            return DEFECT

        return COOP

# %%
import math
import random

class K81R(Strategy):
    def reset(self):
        self.L4 = [[0.0 for _ in range(2)] for _ in range(8)]
        self.T4 = 0
        self.T5 = 0
        self.T6 = 25
        self.T9 = 5
        self.M = 0
        self.last_opp = None
        self.score = 0
        self.opp_score = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.M += 1
        self.last_opp = opp_move
        self.score += r_self
        self.opp_score += r_opp

    def act(self, state):
        if self.M == 0:
            return self.COOP

        J = self.last_opp
        K = self.score
        L = self.opp_score
        M = self.M + 1

        if M == 2 and J == 1:
            self.T9 = 9

        if M < self.T9:
            return self.COOP

        if self.T5 > 7:
            self.T5 -= 8

        if J == 0:
            idx = self.T5 % 8
            if 0 <= idx < 8:  # ADD BOUNDS CHECK
                self.L4[idx][0] += 1

        if L <= K + self.T6:
            D4 = self.T4 % 8
            A1 = self.L4[D4][0]
            A2 = self.L4[D4][1] if self.L4[D4][1] != 0 else 1.0
            A3 = A1 / A2
            A = 3 * A3
            B = A + A3 + 1
            S1 = max(range(8), key=lambda i: ([A]*4 + [B]*4)[i])
            move = self.DEFECT if S1 < 5 else self.COOP
        else:
            move = J

        self.T5 = self.T4

        if M % 10 == 0:
            for c in range(8):
                self.L4[c][0] *= 9
            self.T6 += 1

        if self.T4 > 4:
            self.T4 -= 4

        self.T4 = self.T4 * 2 + move
        return move


class K82R(Strategy):
    def reset(self):
        self.X = 0.75
        self.I5 = 0
        self.D4 = 0.0
        self.I1 = 0
        self.I2 = 0
        self.I3 = 1
        self.M = 0
        self.last_opp = None

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.M += 1
        self.last_opp = opp_move

    def act(self, state):
        if self.M == 0:
            return self.COOP

        J = self.last_opp
        M = self.M + 1
        R = random.random()

        move = J

        if J == 0 and self.I5 > 1:
            self.I5 = 0

        if M < 30:
            return move

        if self.I3 == 0:
            return self.COOP

        if M > 1 and abs(self.D4 / (M - 1.0) - 0.5) < 0.1:
            self.X -= 0.2

        if self.I2 == 1:
            if J == 1:
                self.X = min(1.0, self.X + 0.15)
            return self.COOP

        if R > self.X:
            self.I1 = 1
            return self.DEFECT

        if J == 1:
            self.X = max(0.0, self.X - 0.05)
            self.I2 = 0
            if self.X < 0.3:
                return self.DEFECT
            return move

        self.I2 = 0
        self.I3 = 1 if self.I5 <= 5 else 0
        self.I5 = 0
        self.I1 = 0

        return self.COOP


class K83R(Strategy):
    def reset(self):
        self.JHIS = [0]*5
        self.JTOT = 0
        self.MCNT = 0
        self.M = 0
        self.last_opp = None

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.M += 1
        self.last_opp = opp_move

    def act(self, state):
        if self.M == 0:
            return self.COOP

        J = self.last_opp
        M = self.M + 1
        R = random.random()

        if M <= 5:
            self.JHIS[M-1] = J
            self.JTOT += J
            return self.COOP
        
        idx = self.MCNT % 5  # ADD: Calculate safe index first
        self.JTOT = self.JTOT - self.JHIS[idx] + J
        self.JHIS[idx] = J
        self.MCNT = (self.MCNT + 1) % 5

        return self.DEFECT if R*25 < (self.JTOT*self.JTOT - 1) else self.COOP


class K84R(Strategy):
    def reset(self):
        self.ISIG = 0
        self.DS = 0
        self.JQ = 0
        self.FJD = 0
        self.JDR = 0
        self.FM = 0
        self.M = 0
        self.last_opp = None
        self.score = 0
        self.opp_score = 0

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.M += 1
        self.last_opp = opp_move
        self.score += r_self
        self.opp_score += r_opp

    def act(self, state):
        if self.M == 0:
            return self.DEFECT

        J = self.last_opp
        K = self.score
        L = self.opp_score
        M = self.M + 1

        if J == 1:
            self.FJD += 1

        if self.ISIG == 0:
            self.FM = M

            if self.JQ == 0 and J == 1:
                self.JDR += 1

            if K - L - self.DS - 5*self.JDR*(self.JDR-1)/2 >= 0:
                move = self.COOP
            else:
                self.JQ = J
                return self.DEFECT

            if (self.JQ - J) < 0 or (M - self.ISIG) < 10:
                self.JQ = J
                return move

            if abs(self.FJD - (self.FM-1)/2.0) < (1.5*math.sqrt(self.FM-1)):
                self.ISIG = 1
                self.JQ = J
                return self.DEFECT

            self.JQ = J
            return move

        self.ISIG = M
        self.JQ = 0
        self.JDR = 0
        self.DS = K - L
        return self.DEFECT


class K85R(Strategy):
    def reset(self):
        self.J0 = 0
        self.F0 = 0
        self.F1 = 0
        self.C = 0
        self.D = 0
        self.T = 0
        self.I1 = self.I2 = self.I3 = self.I4 = 0
        self.M = 0
        self.last_opp = None

    def remember(self, my_move, opp_move, r_self, r_opp):
        self.M += 1
        self.last_opp = opp_move

    def act(self, state):
        if self.M == 0:
            return self.COOP

        J = self.last_opp
        M = self.M + 1

        self.J0 = (self.J0 % 1e7)*10 + 5
        self.F0 = (self.F0 % 1e7)*10 + 5

        if self.F1 == 0:
            if J == 0:
                self.I3 += 1
            else:
                self.I4 += 1
        else:
            if J == 0:
                self.I1 += 1
            else:
                self.I2 += 1

        if M > 20:
            A = (self.I1+1e-6)/(self.I2+1e-6)
            B = (self.I3+1e-6)/(self.I4+1e-6)
            if not (0.5 <= A <= 1.5 and 0.5 <= B <= 1.5):
                return self.DEFECT

        if self.T == 1:
            return J

        if self.J0 == 11111111:
            return self.DEFECT

        if self.C == 1:
            self.C = 0
            self.F1 = 0
            return self.COOP

        if M <= 30 and (self.J0 % 100) == 11:
            self.C = 1
            return self.DEFECT

        if self.D == 1:
            self.F1 = 0
            self.D = 0
            return self.DEFECT

        if self.F1 == 0:
            return self.COOP if J == 0 else self.COOP
        else:
            return self.DEFECT if J == 1 else self.COOP

# %%
import random

class K86R(Strategy):
    def reset(self):
        self.IOPPNT = {}
        self.last = 0
        self.M = 0

    def remember(self, agent_move, opponent_move,r1,r2):
        self.M += 1
        self.IOPPNT[self.M] = opponent_move

    def act(self, state):
        MOVEN = self.M + 1
        RANDOM = random.random()
        MYOLD = self.last

        if MOVEN <= 2:
            self.last = 0
            return 0

        if MOVEN <= 7:
            self.last = self.IOPPNT.get(self.M, 0)
            return self.last

        IPREV7 = 0
        for i in range(self.M - 6, self.M + 1):
            IPREV7 += self.IOPPNT.get(i, 0)

        if MYOLD == 0 and IPREV7 <= 2:
            self.last = 0
        elif MYOLD == 0 and IPREV7 > 2:
            self.last = 1
        elif MYOLD == 1 and IPREV7 <= 1:
            self.last = 0
        else:
            self.last = 1

        return self.last


class K87R(Strategy):
    def reset(self):
        self.Z = 0
        self.Q6 = 0.5
        self.S = 0
        self.H = 0
        self.M = 0
        self.last_J = 0

    def remember(self, agent_move, opponent_move, r1, r2):
        self.M += 1
        self.last_J = opponent_move

    def act(self, state):
        R = random.random()
        M = self.M + 1
        J = self.last_J

        if M == 1:
            self.Z = 0
            self.Q6 = 0.5
            self.S = 0
            self.H = 0
            return 0

        self.S = 2 * J + self.H + 1

        if self.Z == 0 and J == 1:
            self.Z = 1

        if self.S <= 1:
            self.Q6 = self.Q6 * 0.57 + 0.43
        elif self.S == 4:
            self.Q6 = 0.74 * self.Q6 + 0.104
        else:
            self.Q6 = 0.5 * self.Q6

        self.H = 1

        if R > self.Q6:
            return 1

        self.H = 0
        return 0


class K88R(Strategy):
    def reset(self):
        self.MMC = 0
        self.LMV = 0
        self.MP = 0
        self.MMV = 0
        self.MP2 = 0
        self.MMD = 1
        self.DFLG = 0
        self.PRC = 0.0
        self.PRD = 0.0
        self.M = 0
        self.last_J = 0

    def remember(self, agent_move, opponent_move, r1, r2):
        self.M += 1
        self.last_J = opponent_move

    def act(self, state):
        J = self.last_J
        M = self.M + 1
        R = random.random()

        K88R = 0

        if M == 1:
            self.reset()

        if M >= 2:
            if self.MMV != 0:
                self.MMD += 1
                self.MP2 += J
                self.PRD = float(self.MP2) / float(self.MMD)
            else:
                self.MMC += 1
                self.MP += J
                self.PRC = float(self.MP) / float(self.MMC)

        if M > 4:
            if J == 1 and self.DFLG == 0:
                self.DFLG = 1
                K88R = 0
            else:
                if self.MMV == 0 and R < self.PRC:
                    K88R = 1
                if self.MMV == 1 and R < self.PRD:
                    K88R = 1

        self.MMV = self.LMV
        self.LMV = K88R

        return K88R


class K89R(Strategy):
    def reset(self):
        self.SC = [0] * 6
        self.SL = [1] * 6
        self.ST = [0] * 5
        self.GT = [0] * 5
        self.TM = [0] * 6
        self.CN = 10
        self.TM[5] = 0
        self.SL[5] = 1
        self.CSRC = 5
        self.MYLM = 1
        self.HLM = 0
        self.M = 0
        self.last_J = 0
        self.MYSC = 0

    def remember(self, agent_move, opponent_move, r1, r2):
        self.M += 1
        self.last_J = opponent_move

    def act(self, state):
        HCM = self.last_J
        MYSC = self.MYSC

        while True:
            CODE = self.CN // 10

            if CODE < 0 or CODE >= len(self.SL):
                self.CN += 10
                continue

            if 10 * CODE == self.CN:
                self.SC[CODE] = MYSC

            if self.SL[CODE] == 1:
                self.CN += 1
                self.TM[CODE] += 1

                if CODE == 1:
                    return 0
                elif CODE == 2:
                    return 1
                elif CODE == 3:
                    self.MYLM = 1 - self.MYLM
                    return self.MYLM
                elif CODE == 4:
                    return 1 if HCM == 1 else 0
                elif CODE == 5:
                    if HCM == 1 and self.HLM == 1:
                        return 1
                    self.HLM = HCM
                    return 0
                elif CODE == 6:
                    SGT = 0
                    for i in range(5):
                        self.ST[i] = self.SC[i + 1] - self.SC[i]
                        SGT += self.ST[i]
                        self.GT[i] += self.ST[i]

                    MEAN = SGT / self.CSRC if self.CSRC != 0 else 0
                    AMEAN = 9 * MEAN / 10

                    self.CSRC = 0

                    for i in range(5):
                        if self.SL[i] == 1:
                            if self.ST[i] < AMEAN:
                                self.SL[i] = 0
                            else:
                                if self.TM[i] != 0 and (10 * self.GT[i] / self.TM[i]) > AMEAN:
                                    self.SL[i] = 1

                        if self.SL[i] == 1:
                            self.CSRC += 1

                    self.CN = 10
                    continue

            self.CN += 10


class K90R(Strategy):
    def reset(self):
        self.jold = 0
        self.M = 0
        self.last_J = 0

    def remember(self, agent_move, opponent_move, r1, r2):
        self.M += 1
        self.last_J = opponent_move

    def act(self, state):
        J = self.last_J
        M = self.M + 1

        if M == 1:
            self.jold = 0

        K90R = 0

        if self.jold == 1 and J == 1:
            K90R = 1

        self.jold = J
        return K90R

# %%
import random

class K91R(Strategy):
    def reset(self):
        self.X = 0.999
        self.PX = 0.001
        self.Y = 0.001
        self.PY = 0.999
        self.Z = 0.999
        self.PZ = 0.001
        self.W = 0.001
        self.PW = 0.999

        self.QC = [1.999, 1.999, 0.001, 0.001]
        self.QN = [2, 2, 2, 2]

        self.E = [0] * 11

        self.IPOL = [
            [0, 1, 1, 0],
            [1, 1, 1, 0],
            [1, 1, 0, 0],
            [1, 0, 0, 1],
            [1, 1, 1, 0],
            [0, 1, 1, 0],
            [1, 0, 0, 1],
            [0, 1, 0, 0],
            [1, 1, 0, 1],
            [1, 0, 0, 1],
            [0, 0, 1, 1],
        ]

        self.IOLD = 0
        self.N = 0
        self.M = 0
        self.last_J = 0
        self.last = 0

    def remember(self, agent_move, opponent_move, r1, r2):
        self.M += 1
        self.last_J = opponent_move

    def act(self, state):
        J = self.last_J
        M = self.M + 1

        if M == 1:
            self.reset()
            return 0

        # update stats
        if M > 2:
            if self.N >= 0:
                if J == 0:
                    self.QC[self.N] += 1
                self.QN[self.N] += 1

        if self.N == 0:
            self.X = self.QC[0] / self.QN[0]
            self.PX = 1 - self.X
        elif self.N == 1:
            self.Z = self.QC[1] / self.QN[1]
            self.PZ = 1 - self.Z
        elif self.N == 2:
            self.Y = self.QC[2] / self.QN[2]
            self.PY = 1 - self.Y
        elif self.N == 3:
            self.W = self.QC[3] / self.QN[3]

        X, PX = self.X, self.PX
        Y, PY = self.Y, self.PY
        Z, PZ = self.Z, self.PZ
        W = self.W
        PW = self.PW

        E = [0] * 11

        E[0] = (3 * Z) / (Z + PX + 1e-9)
        E[1] = (3 * (Y * Z + W * PZ) + 5 * Z * PX + PX * PZ) / (Y * Z + W * PZ + PX + Z * PX + PX * PZ + 1e-9)
        E[2] = (3 * W * Y + 5 * W * PX + PX * PZ) / (W * Y + 2 * W * PX + PX * PZ + 1e-9)
        E[3] = (3 * W * PY + 5 * Z * PX + PX * PY) / (W * PY + PX * PY + Z * PX + PX * PY + 1e-9)
        E[4] = (3 * Z + 5 * X * Z + Z * PX) / (1 - X * Y - W * PX + 2 * Z + 1e-9)
        E[5] = (8 * W * Z + Z * PX) / (2 * W * Z + W * PY + Z * PX + 1e-9)
        E[6] = (3 * Z * PY + 5 * X * Z + Z * PY) / (2 * Z * PY + PW * PY + X * Z + 1e-9)
        E[7] = (3 * (Y * Z + W * PZ) + 5 * (Z * PW + W * X) + 1 - X * Y - Z * PY) / (Y * Z + W * PZ + 2 - 2 * X * Y - W * PX + Z * PW + W * X - Z * PY + 1e-9)
        E[8] = (3 * W * Y + 5 * W + 1 - X * Y - Z * PY) / (2 * W + 1 - X * Y - Z * PY + 1e-9)
        E[9] = (3 * W * PY + 5 * (Z * PW + W * X) + PY) / (PY + Z * PW + W * X + PY + 1e-9)
        E[10] = (5 * W + PY) / (W + PY + 1e-9)

        ibest = max(range(11), key=lambda i: E[i])

        IOLD = self.last
        N = 2 * IOLD + J

        action = self.IPOL[ibest][N]

        self.N = N
        self.last = action
        return action


class K93R(Strategy):
    def reset(self):
        pass

    def remember(self, agent_move, opponent_move, r1, r2):
        pass

    def act(self, state):
        return self.COOP if random.random() >= 0.5 else self.DEFECT

# %% [markdown]
# ## Game Match Simulations

# %%
import os
import json
import random
from concurrent.futures import ProcessPoolExecutor


def run_match(args):
    S1, S2, N, T = args

    random.seed(42 + os.getpid())

    s1 = S1()
    s2 = S2()

    state = MatchState(N=N, T=T)

    games = state.match_play(s1, s2)

    name1 = S1.__name__
    name2 = S2.__name__

    os.makedirs("logs", exist_ok=True)

    filepath = f"logs/{name1}_vs_{name2}.json"

    with open(filepath, "w") as f:
        json.dump({
            "player1": name1,
            "player2": name2,
            "games": games
        }, f)

    return {
        "player1": name1,
        "player2": name2,
        "n_games": len(games)
    }


def run_tournament(strategy_classes, N=5, T=100, workers=None):

    pairs = [(S1, S2, N, T) for S1 in strategy_classes for S2 in strategy_classes]

    results = []

    with ProcessPoolExecutor(max_workers=workers) as executor:
        for result in executor.map(run_match, pairs):
            results.append(result)
            print(f"{result['player1']} vs {result['player2']}: {result['n_games']} games")

    os.makedirs("logs", exist_ok=True)

    with open("logs/summary.json", "w") as f:
        json.dump(results, f, indent=2)

    return results

# %%
# ----------------------------
# USAGE
# ----------------------------
# if __name__ == "__main__":

strategy_classes = [
    # TitForTat, TitForTwoTats, GrimTrigger, Pavlov,
    K59R, K73R, K74R, K74RXX, K75R, K92R,
    KPavlovC, KRandomC, KTF2TC, KTitForTatC, GRASR,
    K31R, K32R, K33R, K34R, K35R, K36R, K37R, K38R, K39R,
    K40R, K41R, K42R, K43R, K44R, K45R, K46R, K47R, K48R,
    K49R, K50R, K51R, K52R, K53R, K54R, K55R, K56R, K57R,
    K58R, K60R, K61R, K62R, K63R, K64R, K65R, K66R, K67R,
    K68R, K69R, K70R, K71R, K72R, K76R, K77R, K78R, K79R,
    K80R, K81R, K82R, K83R, K84R, K85R, K86R, K87R, K88R,
    K90R, K91R, K92R, K93R
]

run_tournament(strategy_classes, N=5, T=100, workers=None)

# %% [markdown]
# ## Data Preparation

# %%
import json
import pandas as pd
import glob
import os


def load_game_df(log_dir="logs", include_history=False):
    rows = []
    global_game_id = 0

    for file in sorted(glob.glob(f"{log_dir}/*.json")):
        if "summary" in file:
            continue

        with open(file, "r") as f:
            data = json.load(f)

        p1 = data["player1"]
        p2 = data["player2"]

        filename = os.path.basename(file)

        for local_game_id, game in enumerate(data["games"]):

            row = {
                "global_game_id": global_game_id,
                "match_id": f"{p1}_vs_{p2}",
                "local_game_id": local_game_id,
                "file": filename,
                "player1": p1,
                "player2": p2,
            }

            # OPTIONAL: include full history directly
            if include_history:
                row["history"] = game["history"]

            rows.append(row)
            global_game_id += 1

    return pd.DataFrame(rows)

# %%
df = load_game_df("logs", include_history=True)
row = df[df["global_game_id"] == 10].iloc[0]
history = row["history"]

# %%
df.loc[0, "history"]

# %%
df.shape

# %%
df["match_id"].nunique()

# %%
# 1. set index
df = df.set_index("global_game_id")

# 2. shuffle
df = df.sample(frac=1, random_state=42)

# 3. split
train_size = int(0.7 * len(df))
valid_size = int(0.85 * len(df))
train_df = df.iloc[:train_size]
valid_df = df.iloc[train_size:valid_size]
test_df = df.iloc[valid_size:]


# %% [markdown]
# ## LSTM
# - predicting both
#     - predicting 10 steps ahead ROC Uniform
#     - predicting 10 steps ahead ROC weight early
#     - predicting 10 steps ahead ROC weight last
# - predicting opponent only
#     - predicting 10 steps ahead ROC Uniform
#     - predicting 10 steps ahead ROC weight early
#     - predicting 10 steps ahead ROC weight last

# %%
train_df.iloc[0]["history"]

# %%
train_df.iloc[0]

# %% [markdown]
# ### LSTM Model

# %%
import torch
from torch.utils.data import Dataset
LAG = 50

class IPDDataset(Dataset):
    def __init__(self, df, seq_len=LAG, target="opponent"):
        self.X = []
        self.y = []

        PAD = 2  # after remapping

        for _, row in df.iterrows():
            history = row["history"]

            # map values: -1→0, 0→1, 1→2
            history_ab = [[step[0], step[1]] for step in history]

            for t in range(1, len(history_ab)):
                past = history_ab[:t]

                seq = past[-seq_len:]

                if len(seq) < seq_len:
                    pad_len = seq_len - len(seq)
                    seq = [[PAD, PAD]] * pad_len + seq

                next_step = history_ab[t]

                if target == "opponent":
                    label = next_step[1]   # stays to {1,2}
                elif target == "agent":
                    label = next_step[0]
                else:
                    raise ValueError("invalid target")

                self.X.append(seq)
                self.y.append(label)

        self.X = torch.tensor(self.X, dtype=torch.long)   # IMPORTANT
        self.y = torch.tensor(self.y, dtype=torch.long)

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]

# %%
import torch.nn as nn
import torch

class LSTMModel(nn.Module):
    def __init__(self, embed_dim=8, hidden_size=32):
        super().__init__()

        # 3 tokens: PAD(0), 0→1, 1→2
        self.embed = nn.Embedding(
            num_embeddings=3,
            embedding_dim=embed_dim,
            padding_idx=0
        )

        self.lstm = nn.LSTM(
            input_size=embed_dim * 2,  # a + b
            hidden_size=hidden_size,
            batch_first=True
        )

        self.fc = nn.Linear(hidden_size, 2)

    def forward(self, x):
        # x: (B, T, 2)

        a = x[:, :, 0]  # (B, T)
        b = x[:, :, 1]

        a_emb = self.embed(a)  # (B, T, E)
        b_emb = self.embed(b)

        x_emb = torch.cat([a_emb, b_emb], dim=-1)  # (B, T, 2E)

        out, _ = self.lstm(x_emb)
        out = out[:, -1, :]
        out = self.fc(out)

        return out

# %%
from torch.utils.data import DataLoader

dataset = IPDDataset(train_df, seq_len=LAG, target="opponent")
loader = DataLoader(
    dataset,
    batch_size=32,       # bigger batch = more parallel compute
    shuffle=True,
    num_workers=8        # tune based on CPU cores
)

model = LSTMModel()
criterion = nn.CrossEntropyLoss()
optimizer = torch.optim.Adam(model.parameters(), lr=0.001)
# optimizer = torch.optim.SGD(
#     model.parameters(),
#     lr=0.001,
#     momentum=0.9
# )

# %% [markdown]
# ### Run LSTM
# 

# %%
for epoch in range(2):
    total_loss = 0

    for X, y in loader:
        optimizer.zero_grad()

        preds = model(X)
        loss = criterion(preds, y)

        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    print(f"Epoch {epoch}: {total_loss:.4f}")

# %%
torch.save(model.state_dict(), "lstm_ipd.pth")

# %% [markdown]
# ### load model

# %%
model = LSTMModel()
model.load_state_dict(torch.load("lstm_ipd.pth"))
model.eval()

# %%
# example: take from dataset
X, y_true = dataset[0]   # (seq_len, 2)

X = X.unsqueeze(0)       # (1, seq_len, 2)

with torch.no_grad():
    logits = model(X)
    pred = torch.argmax(logits, dim=1).item()

print("Predicted:", pred)
print("Actual:", y_true.item())

# %%
for i in range(10):
    X, y = dataset[i]
    X = X.unsqueeze(0)

    with torch.no_grad():
        pred = torch.argmax(model(X), dim=1).item()

    print(i, pred, y.item())

# %%
dataset = IPDDataset(valid_df, seq_len=10, target="opponent")
loader_valid = DataLoader(
    dataset,
    batch_size=32,       # bigger batch = more parallel compute
    shuffle=False,
    num_workers=8        # tune based on CPU cores
)

# %%


# %%
correct = 0
total = 0

with torch.no_grad():
    for X, y in loader_valid:
        preds = model(X)
        predicted = torch.argmax(preds, dim=1)

        correct += (predicted == y).sum().item()
        total += y.size(0)

print("Accuracy:", correct / total)

# %%
correct = 0
total = 0

with torch.no_grad():
    for X, y in loader_valid:
        print(X,"\nactual: ",y, "\npredicted: ", torch.argmax(model(X), dim=1))
        break

# %%
def truncate_history(history, max_len=LAG):
    if len(history) <= max_len:
        return history
    else:
        return history[-max_len:]

# %%
def pred_opp(history, model):
    X = truncate_history(history)
    X = torch.tensor(X, dtype=torch.long).unsqueeze(0)  # (
    with torch.no_grad():
        logits = model(X)
        pred = torch.argmax(logits, dim=1).item()
    return pred

# %%
def pred_agent(history, strategy = model):
    if isinstance(strategy, LSTMModel):
        X = history[-LAG:]
        X = torch.tensor(X, dtype=torch.long).unsqueeze(0)  # (
        with torch.no_grad():
            logits = strategy(X.flip(dims=[-1]))
            pred = torch.argmax(logits, dim=1).item()
        return pred
    else:
        return strategy(history)

# %%
# appending history with new steps
def append_history(history, new_step):
    new_entry = [new_step[0], new_step[1]]
    history.append(new_entry)
    return history

# %%
state = MatchState(N=1, T=100, e=0.1)
history = state.game_play(TitForTat(), TitForTat())
print(history)


# %%
state = MatchState(N=1, T=100, e=0.1)
history = state.game_play(TitForTat(), TitForTat())
print(history)

# %%
history =  []
# example usage
for i in range(LAG):
    append_history(history, [2, 2])  # pad with (2,2)
    
history.extend([t[:2] for t in state.history])

for i in range(20):
    pred_opp_action = pred_opp(history, model)
    pred_agent_action = pred_agent(history, model)

    print(f"Embedded Predicted Opponent: {pred_opp_action}, Predicted Agent: {pred_agent_action}")

    next_step = [pred_agent_action, pred_opp_action] 
    append_history(history, next_step)

# %%
print("Final History:", history)

# %%


# %%
class ModelTrajectory:
    def __init__(self, model, device="cpu"):
        self.model = model.to(device)
        self.device = device
        self.history = []

    def predict(self, seq):
        self.history.append(seq.cpu().numpy().tolist())

        seq = torch.tensor(seq, dtype=torch.long).unsqueeze(0).to(self.device)

        with torch.no_grad():
            logits = self.model(seq)
            pred = torch.argmax(logits, dim=1).item()

        return pred

# %%
# correct = 0
# total = 0

# with torch.no_grad():
#     for X, y in loader:
#         preds = model(X)
#         predicted = torch.argmax(preds, dim=1)

#         correct += (predicted == y).sum().item()
#         total += y.size(0)

# print("Accuracy:", correct / total)

# %%
def rollout(model, init_seq, horizon, agent_policy):
    model.eval()

    seq = init_seq.clone()   # (seq_len, 2)
    preds = []

    for _ in range(horizon):
        x = seq.unsqueeze(0)   # (1, T, 2)

        with torch.no_grad():
            logits = model(x)
            pred_b = torch.argmax(logits, dim=1).item()

        a = agent_policy(seq)

        new_step = torch.tensor([a, pred_b], dtype=torch.long)
        preds.append(pred_b)

        seq = torch.cat([seq[1:], new_step.unsqueeze(0)], dim=0)

    return preds

# %%
def agent_policy(seq):
    return 1

init_seq, _ = dataset[0]

# Convert init_seq to Long type if it's a float tensor
if init_seq.dtype != torch.long:
    init_seq = init_seq.long()

future = rollout(model, init_seq, horizon=10, agent_policy=agent_policy)

print(future)

# %%
# for strategy in [K34R, K35R, K36R, K37R, K38R, K39R]:
#     future = rollout(model, init_seq, 20, strategy)
#     print(f"Future actions for {strategy.__name__}: {future}")


