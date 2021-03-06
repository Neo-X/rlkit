"""
General networks for pytorch.

Algorithm-specific networks should go else-where.
"""
import torch
from torch import nn as nn
from torch.nn import functional as F
from torch.autograd import Variable

from rlkit.policies.base import Policy
from rlkit.torch import pytorch_util as ptu
from rlkit.torch.core import PyTorchModule
from rlkit.torch.data_management.normalizer import TorchFixedNormalizer
from rlkit.torch.modules import LayerNorm
import numpy as np

def identity(x):
    return x


class Mlp(PyTorchModule):
    def __init__(
            self,
            hidden_sizes,
            output_size,
            input_size,
            init_w=3e-3,
            hidden_activation=F.relu,
            output_activation=identity,
            hidden_init=ptu.fanin_init,
            b_init_value=0.1,
            layer_norm=False,
            layer_norm_kwargs=None,
    ):
        self.save_init_params(locals())
        super().__init__()

        if layer_norm_kwargs is None:
            layer_norm_kwargs = dict()

        self.input_size = input_size
        self.output_size = output_size
        self.hidden_activation = hidden_activation
        self.output_activation = output_activation
        self.layer_norm = layer_norm
        self.fcs = []
        self.layer_norms = []
        in_size = input_size

        for i, next_size in enumerate(hidden_sizes):
            fc = nn.Linear(in_size, next_size)
            in_size = next_size
            hidden_init(fc.weight)
            fc.bias.data.fill_(b_init_value)
            self.__setattr__("fc{}".format(i), fc)
            self.fcs.append(fc)

            if self.layer_norm:
                ln = LayerNorm(next_size)
                self.__setattr__("layer_norm{}".format(i), ln)
                self.layer_norms.append(ln)

        self.last_fc = nn.Linear(in_size, output_size)
        self.last_fc.weight.data.uniform_(-init_w, init_w)
        self.last_fc.bias.data.uniform_(-init_w, init_w)

    def forward(self, input, return_preactivations=False):
        h = input
        for i, fc in enumerate(self.fcs):
            h = fc(h)
            if self.layer_norm and i < len(self.fcs) - 1:
                h = self.layer_norms[i](h)
            h = self.hidden_activation(h)
        preactivation = self.last_fc(h)
        output = self.output_activation(preactivation)
        if return_preactivations:
            return output, preactivation
        else:
            return output

class BackupMlp(PyTorchModule):
    def __init__(
            self,
            hidden_sizes,
            output_size,
            input_size,
            init_w=3e-3,
            hidden_activation=F.relu,
            output_activation=identity,
            hidden_init=ptu.fanin_init,
            b_init_value=0.1,
            layer_norm=False,
            layer_norm_kwargs=None,
    ):
        self.save_init_params(locals())
        super().__init__()

        if layer_norm_kwargs is None:
            layer_norm_kwargs = dict()

        self.input_size = input_size
        self.output_size = output_size
        self.hidden_activation = hidden_activation
        self.output_activation = output_activation
        self.layer_norm = layer_norm
        self.fcs = []
        self.layer_norms = []
        in_size = input_size

        for i, next_size in enumerate(hidden_sizes):
            fc = nn.Linear(in_size, next_size)
            in_size = next_size
            hidden_init(fc.weight)
            fc.bias.data.fill_(b_init_value)
            self.__setattr__("fc{}".format(i), fc)
            self.fcs.append(fc)

            if self.layer_norm:
                ln = LayerNorm(next_size)
                self.__setattr__("layer_norm{}".format(i), ln)
                self.layer_norms.append(ln)

        self.last_fc = nn.Linear(in_size, output_size)
        self.last_fc.weight.data.uniform_(-init_w, init_w)
        self.last_fc.bias.data.uniform_(-init_w, init_w)

    def forward(self, input, return_preactivations=False):
        h = input
        for i, fc in enumerate(self.fcs):
            h = fc(h)
            if self.layer_norm and i < len(self.fcs) - 1:
                h = self.layer_norms[i](h)
            h = self.hidden_activation(h)
        preactivation = self.last_fc(h)
        output = self.output_activation(preactivation)
        if return_preactivations:
            return output, preactivation
        else:
            return output

class ObjectMlp(PyTorchModule):
    def __init__(
            self,
            hidden_sizes,
            output_size,
            input_size,
            init_w=3e-3,
            hidden_activation=F.relu,
            output_activation=identity,
            hidden_init=ptu.fanin_init,
            b_init_value=0.1,
            layer_norm=False,
            layer_norm_kwargs=None,
            index_to_object=[0,0,0,0,1,1,2,2,3,3],
            objects=['agent', 'target', 'enemy', 'enemy'],
    ):
        self.save_init_params(locals())
        super().__init__()

        if layer_norm_kwargs is None:
            layer_norm_kwargs = dict()
        self.TARGET = Variable(torch.FloatTensor([[1.,0.]]), requires_grad=False)
        self.ENEMY =  Variable(torch.FloatTensor([[0.,1.]]), requires_grad=False)
        self.input_size = input_size
        self.output_size = output_size
        self.hidden_activation = hidden_activation
        self.output_activation = output_activation
        self.layer_norm = layer_norm
        self.fcs = []
        self.layer_norms = []
        in_size = input_size
        assert(input_size == len(index_to_object))
        self.index_to_object = index_to_object
        self.objects = objects

        def mlp(layer_sizes, scope):
            in_size = layer_sizes[0]
            layers = []
            for i, next_size in enumerate(layer_sizes[1:]):
                fc = nn.Linear(in_size, next_size)
                in_size = next_size
                hidden_init(fc.weight)
                fc.bias.data.fill_(b_init_value)
                layers.append(fc)
                self.__setattr__(scope+"fc{}".format(i), fc)
            return layers

        self.affordance_mlp = mlp([2,20], 'affordance')
        self.weight_mlp = mlp([4, 10,1], 'weight')
        self.translator_mlp = mlp([20+4+2, 10,10, output_size], 'translator')

        # self.last_fc = nn.Linear(in_size, output_size)
        # self.last_fc.weight.data.uniform_(-init_w, init_w)
        # self.last_fc.bias.data.uniform_(-init_w, init_w)
    def _run_mlp(self, input, mlp, activation, last_activation):
        h = input
        for i, fc in enumerate(mlp[:-1]):
            h = fc(h)
            if self.layer_norm and i < len(self.fcs) - 1:
                h = self.layer_norms[i](h)
            h = activation(h)
        preactivation = mlp[-1](h)
        output = last_activation(preactivation)
        return output

    def _apply_translator(self, agent, obj, affordance):
        input = torch.cat((agent, obj, affordance), dim=1)
        p_a = self._run_mlp(input, self.translator_mlp, F.relu, identity)
        return p_a

    def forward(self, input, return_preactivations=False):
        agent = input[:,:4]
        target = input[:, 4:6]
        enemy_1 = input[:, 6:8]
        enemy_2 = input[:, 8:10]
        batch = input.shape[0]
        TARGET = self.TARGET.expand((batch,2))
        ENEMY = self.ENEMY.expand((batch,2))
        target_aff = self._run_mlp(TARGET, self.affordance_mlp, F.relu, identity)
        #print("target_aff", target_aff)
        #import pdb; pdb.set_trace()
        enemy_aff = self._run_mlp(ENEMY, self.affordance_mlp, F.relu, identity)
        actions = [self._apply_translator(agent, target, target_aff),
                   self._apply_translator(agent, enemy_1, enemy_aff),
                   self._apply_translator(agent, enemy_2, enemy_aff)]
        final_action = sum(actions)

        p_a = [F.softmax(a, dim=1) for a in actions]
        p_a_tot = F.softmax(final_action, dim=1)
        max, indices = p_a_tot.data.max(dim=1)
        self.weights = [float(p[0, int(indices[0])]) for p in p_a]
        print(self.weights)
        self.p_a_tot = p_a_tot.data.numpy()
        #self.myactions = actions.data.numpy()
        #import pdb; pdb.set_trace()
        return final_action


class FullObjectMlp(PyTorchModule):
    def __init__(
            self,
            hidden_sizes,
            output_size,
            input_size,
            object_index,
            object_classes,
            num_tasks,
            init_w=3e-3,
            hidden_activation=F.relu,
            output_activation=identity,
            hidden_init=ptu.fanin_init,
            b_init_value=0.1,
            layer_norm=False,
            layer_norm_kwargs=None,
    ):
        self.save_init_params(locals())
        super().__init__()

        if layer_norm_kwargs is None:
            layer_norm_kwargs = dict()
        num_classes = len(set(object_classes))-1 #Agent is not a class
        self.AGENT_SIZE = 4
        self.AFF_SIZE = 20
        self.object_classes = object_classes
        self.object_index = object_index
        self.num_tasks = num_tasks
        self.class_variables = []
        for c in range(num_classes):
            arr = np.zeros((1,num_classes))
            arr[0][c] =1.0
            self.class_variables.append(Variable(torch.FloatTensor(arr), requires_grad=False))
        self.task_variables = []
        self.task_tensor = torch.eye(self.num_tasks)
        self.input_size = input_size
        self.output_size = output_size
        self.hidden_activation = hidden_activation
        self.output_activation = output_activation
        self.layer_norm = layer_norm
        self.fcs = []
        self.layer_norms = []
        in_size = input_size
        def mlp(layer_sizes, scope, last_layer_init=None):
            in_size = layer_sizes[0]
            layers = []
            for i, next_size in enumerate(layer_sizes[1:]):
                fc = nn.Linear(in_size, next_size)
                in_size = next_size
                if i == len(layer_sizes[:1])-1 and last_layer_init is not None:
                    last_layer_init(fc.weight)
                else:
                    hidden_init(fc.weight)
                fc.bias.data.fill_(b_init_value)
                layers.append(fc)
                self.__setattr__(scope+"fc{}".format(i), fc)
            return layers
        self.num_classes = num_classes
        self.affordance_mlp = mlp([num_classes,20,self.AFF_SIZE], 'affordance')
        self.weight_mlp = mlp([self.AGENT_SIZE+num_classes, 10,1], 'weight')
        self.translator_mlp = mlp([self.AFF_SIZE+self.AGENT_SIZE+2, 10,10, output_size], 'translator')
        self.task_attention_mlp = mlp([self.num_tasks+num_classes+self.AGENT_SIZE, 10, 1,], 'task_attention', ptu.zeros_init)
        # self.last_fc = nn.Linear(in_size, output_size)
        # self.last_fc.weight.data.uniform_(-init_w, init_w)
        # self.last_fc.bias.data.uniform_(-init_w, init_w)
    def _run_mlp(self, input, mlp, activation, last_activation):
        h = input
        for i, fc in enumerate(mlp[:-1]):
            h = fc(h)
            if self.layer_norm and i < len(self.fcs) - 1:
                h = self.layer_norms[i](h)
            h = activation(h)
        preactivation = mlp[-1](h)
        output = last_activation(preactivation)
        return output

    def _apply_translator(self, agent, obj, affordance):
        #sizes = [agent.size()[0], obj.size()[0], affordance.size()[0]]
        input = torch.cat((agent, obj, affordance), dim=1)
        p_a = self._run_mlp(input, self.translator_mlp, F.relu, identity)
        return p_a

    def forward(self, input, return_preactivations=False):
        task = input[:, 0]
        task = task.type(torch.LongTensor).data
        agent = input[:,1:self.object_index[1]]
        objects = []
        batch = input.shape[0]
        cls_vars = [self.class_variables[i].expand((batch,self.num_classes))
                    for i in range(self.num_classes)]
        for i in range(1,len(self.object_index)-1):
            obj = input[:, self.object_index[i]:self.object_index[i+1]]
            cls = self.object_classes[i]-1
            cls_var = cls_vars[cls]
            objects.append((obj,cls,cls_var))
        #import pdb; pdb.set_trace()
        task_input =Variable( self.task_tensor[task], requires_grad=False)
        obj = input[:, self.object_index[-1]:]
        cls = self.object_classes[-1]-1
        cls_var = cls_vars[cls]
        objects.append((obj,cls,cls_var))

        affordances = [self._run_mlp(cls_var,self.affordance_mlp, F.relu, identity) for
                       cls_var in cls_vars]

        weights = []

        
        # if input.size()[0] == 128:
        #     import pdb; pdb.set_trace()
        actions = []
        for obj, cls, cls_var in objects:
            actions.append(self._apply_translator(agent, obj, affordances[cls]))
            weights.append(self._run_mlp( torch.cat((task_input, cls_var, agent), dim=1),
                                          self.task_attention_mlp, F.relu, identity))
        weights_ = torch.cat(weights, dim=1)
        #import pdb; pdb.set_trace()
        softweights = torch.unsqueeze(F.softmax(weights_, dim=1), dim=2)
        stacked_actions = torch.stack(actions, dim=1)
        weighted_actions = stacked_actions*softweights
        #import pdb; pdb.set_trace()
        final_action = torch.sum(weighted_actions, dim=1)

        p_a = [F.softmax(a, dim=1) for a in actions]
        p_a_tot = F.softmax(final_action, dim=1)
        max, indices = p_a_tot.data.max(dim=1)
        self.weights = [float(w[0]) for w in softweights[0]]# [float(p[0, int(indices[0])]) for p in p_a]
        # print(self.weights)
        self.p_a_tot = p_a_tot.data.numpy()
        #self.myactions = actions.data.numpy()
        #import pdb; pdb.set_trace()
        return final_action
    
class FlattenMlp(Mlp):
    """
    Flatten inputs along dimension 1 and then pass through MLP.
    """

    def forward(self, *inputs, **kwargs):
        flat_inputs = torch.cat(inputs, dim=1)
        return super().forward(flat_inputs, **kwargs)


class MlpPolicy(Mlp, Policy):
    """
    A simpler interface for creating policies.
    """

    def __init__(
            self,
            *args,
            obs_normalizer: TorchFixedNormalizer = None,
            **kwargs
    ):
        self.save_init_params(locals())
        super().__init__(*args, **kwargs)
        self.obs_normalizer = obs_normalizer

    def forward(self, obs, **kwargs):
        if self.obs_normalizer:
            obs = self.obs_normalizer.normalize(obs)
        return super().forward(obs, **kwargs)

    def get_action(self, obs_np):
        actions = self.get_actions(obs_np[None])
        return actions[0, :], {}

    def get_actions(self, obs):
        return self.eval_np(obs)


class TanhMlpPolicy(MlpPolicy):
    """
    A helper class since most policies have a tanh output activation.
    """
    def __init__(self, *args, **kwargs):
        self.save_init_params(locals())
        super().__init__(*args, output_activation=torch.tanh, **kwargs)
