import fnmatch
from collections import OrderedDict
from typing import Union, Optional, List

import torch


class AttentionExtract(torch.nn.Module):
    # defaults should cover a significant number of timm models with attention maps.
    default_node_names = ['*attn.softmax']
    default_module_names = ['*attn_drop']

    def __init__(
            self,
            model: Union[torch.nn.Module],
            names: Optional[List[str]] = None,
            mode: str = 'eval',
            method: str = 'fx',
            hook_type: str = 'forward',
    ):
        """ Extract attention maps (or other activations) from a model by name.

        Args:
            model: Instantiated model to extract from.
            names: List of concrete or wildcard names to extract. Names are nodes for fx and modules for hooks.
            mode: 'train' or 'eval' model mode.
            method: 'fx' or 'hook' extraction method.
            hook_type: 'forward' or 'forward_pre' hooks used.
        """
        super().__init__()
        assert mode in ('train', 'eval')
        if mode == 'train':
            model = model.train()
        else:
            model = model.eval()

        assert method in ('fx', 'hook')
        if method == 'fx':
            # names are activation node names
            from timm.models._features_fx import get_graph_node_names, GraphExtractNet

            node_names = get_graph_node_names(model)[0 if mode == 'train' else 1]
            matched = []
            names = names or self.default_node_names
            for n in names:
                matched.extend(fnmatch.filter(node_names, n))
            if not matched:
                raise RuntimeError(f'No node names found matching {names}.')

            self.model = GraphExtractNet(model, matched)
            self.hooks = None
        else:
            # names are module names
            assert hook_type in ('forward', 'forward_pre')
            from timm.models._features import FeatureHooks

            module_names = [n for n, m in model.named_modules()]
            matched = []
            names = names or self.default_module_names
            for n in names:
                matched.extend(fnmatch.filter(module_names, n))
            if not matched:
                raise RuntimeError(f'No module names found matching {names}.')

            self.model = model
            self.hooks = FeatureHooks(matched, model.named_modules(), default_hook_type=hook_type)

        self.names = matched
        self.mode = mode
        self.method = method

    def forward(self, x):
        if self.hooks is not None:
            self.model(x)
            output = self.hooks.get_output(device=x.device)
        else:
            output = self.model(x)
            output = OrderedDict(zip(self.names, output))
        return output
