## Sequence-to-Sequence

This example implements seq2seq with Redco. 
It supports 
* assigning a dataset from [datasets](https://github.com/huggingface/datasets) (XSUM by default)
* assigning a seq2seq model from [transformers](https://github.com/huggingface/transformers) (bart-base by default)
* multi-host running

### Requirement

Install Redco
```shell
pip install redco==0.4.8
```

### Usage

```shell
python main.py \
  --dataset_name xsum \
  --model_name_or_path google/flan-t5-xl \
  --n_model_shards 8
```
* `--n_model_shards`: number of pieces to split your large model, 1 by default (pure data parallelism). 

See `def main(...)` in [main.py](main.py) for all the tunable arguments. 


#### For Multi-host Envs
```
python main.py \
--coordinator_address 192.168.0.1:1234 \ 
--num_processes 2 \
--process_id 1 \
...
```
* `--num_processes`: number of hosts.
* `--coordinator_address`: the ip of host 0 with an arbitrary available port number.
* `--process_id`: id of the current host (should vary across all hosts).

