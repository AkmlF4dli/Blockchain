import sys
import hashlib
import json
import requests
import uuid

from time import time
from uuid import uuid4

from flask import Flask, render_template
from flask.globals import request
from flask.json import jsonify

from urllib.parse import urlparse

class Blockchain(object):
    difficulty_bits = 20
    difficulty_target = 2**(256 - difficulty_bits)

    def hash_block(self, block):
      block_encoded = json.dumps(block, sort_keys=True).encode()
      inner_hash = hashlib.sha256(block_encoded).digest()
      return hashlib.sha256(inner_hash).hexdigest()


    def adddelay(self):    
        self.delaytransaction.append({
             "amount": self.amount,
             "recipient": self.recipient,
             "sender": self.sender,
        })

    def __init__(self):
      self.initial_reward = 50.0
      self.halving_interval = 210000
      self.addnode = ""
      self.nodes = []

      self.users = '''{
      
      }'''
      self.user = json.loads(self.users)      
      self.delaytransaction = []

      self.sender = ""
      self.recipient = ""
      self.amount = ""
      self.password = ""
      
      self.chain = []

      self.current_transaction = []

      self.current_pof = []

      genesis_hash = self.hash_block("ini genesis hash")

      self.append_block(
            hash_of_previous_block = genesis_hash,
            nonce = self.proof_of_work(0, genesis_hash, [])
      )

# multiple nodes
    def add_nodes(self):
        self.nodes.append(self.addnode)
    
    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index == len(chain):
            block = chain[current_index]

            if block['hash_of_previous_block'] != self.hash_block[last_block]:
                return False

            if not self.valid_proof(
                    address_index,
                    block['hash_of_previous_block'],
                    block['transaction'],
                    block['nonce']):
                    return False

            last_block = block
            current_block += 1

        return True

    def update_blockchain(self):
        neighbours = self.nodes
        new_chain = None

        max_length = len(self.chain)

        for node in neighbours:
            response = requests.get(f'http://{node}/blockchain')

            if response.status_code == 200:
                length = response.json()['length']
                chain = response.json()['chain']
                user = chain[0].get('user', {})
                
                if length > max_length and self.valid_chain(chain):
                    max_length = length
                    max_chain = chain
                    new_chain = chain
                    new_user = user

                if new_chain:
                    self.chain = new_chain
                    self.user = new_user
                    return True

        return False

    def add_user(self, password):
      password = self.generate_sha256(password)

      wallet = uuid.uuid4().hex

      blockchain.user[wallet] = {
           "balance": 0,
           "password": password
      }
      return wallet


    def proof_of_work(self, index, hash_of_previous_block, transaction):
      nonce = 0
      timestamp = time()

      while self.valid_proof(index, hash_of_previous_block, transaction, nonce) is False:
        nonce += 1
            
      return nonce, timestamp
      


    def valid_proof(self, index, hash_of_previous_block, transaction, nonce):
        content = f'{index}{hash_of_previous_block}{transaction}{nonce}'.encode()
        first_hash = hashlib.sha256(content).hexdigest()
        content_hash = hashlib.sha256(first_hash.encode()).hexdigest()

        return int(content_hash, 16) < self.difficulty_target
    
    def append_block(self, nonce, hash_of_previous_block):
        block = {
            'index' : len(self.chain),
            'timestamp' : time(),
            'transaction' : self.current_transaction,
            'Pof (proof of work)': self.current_pof,
            'nonce': nonce,
            'hash_of_previous_block': hash_of_previous_block,
            'user' : self.user,

        }

        self.chain.append(block)

        return block

    def generate_sha256(self, password):
        sha256_hash = hashlib.sha256()

        sha256_hash.update(password.encode())
        return sha256_hash.hexdigest()

    def add_transaction(self):
        self.current_transaction.append(self.delaytransaction)
        return self.last_block['index'] + 1

    # def add_transaction(self, delaytransaction):
    #      self.current_transaction.append(self.delaytransaction)
    #      self.delaytransaction = []

    #      return self.last_block['index'] + 1

    def reward(self, miner, amount):
        self.current_pof.append({
            'amount': amount,
            'miner': miner,
        })
    def get_current_reward(self):
        halvings = len(self.chain) // self.halving_interval

        if halvings >= 64:
            return 0
        return self.initial_reward / (2 ** halvings)
         

    @property
    def last_block(self):
        return self.chain[-1]
        
app = Flask(__name__)


blockchain = Blockchain()


@app.route('/', methods=['GET'])
def main():
    return render_template('index.html')

@app.route('/blockchain', methods=['GET'])
def full_chain():
    for node in blockchain.nodes:
        requests.get('http://{node}/nodes/sync')

    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }

    return jsonify(response), 200



@app.route('/mine', methods=['GET'])
def mine_block(): 
    values = request.get_json()

    if values["wallet"] not in blockchain.user:
        return jsonify({
            'status': "Failed",
            'message': "Invalid wallet, make sure wallet is available",
                })

    # blockchain.add_transaction(blockchain.delaytransaction);

    last_block_hash = blockchain.hash_block(blockchain.last_block)
    index = len(blockchain.chain)
    nonce = blockchain.proof_of_work(index, last_block_hash, blockchain.current_transaction)
    block = blockchain.append_block(nonce, last_block_hash)

    for node in blockchain.nodes:
        requests.get(f'http://{node}/nodes/sync')

    response = {
        'status': "Successfully",
        'message': "block successfully create",
        'index': block['index'],
        'hash_of_previous_block': block['hash_of_previous_block'],
        'nonce': block['nonce'],
        'transaction': block['transaction'],
    }

    current_reward = blockchain.get_current_reward()

    blockchain.reward(
        miner=values['wallet'],
        amount=current_reward,
    )
    
    blockchain.user[values['wallet']]['balance'] += current_reward
    
    blockchain.add_transaction()

    blockchain.delaytransaction = []

    return jsonify(response), 200


@app.route('/user/new', methods=['POST'])
def new_user():
    values = request.get_json()
    
    required_fields = ['password']
    if not all(k in values for k in required_fields):
        return jsonify({'message': 'Missing fields'}), 400

    create_user = blockchain.add_user(values['password'])
    return jsonify({'message': 'Successfully created your wallet is: ' + create_user})


@app.route('/transaction/new', methods=['POST'])
def new_transaction():
    values = request.get_json()

    required_fields = ['sender', 'recipient', 'amount', 'password']
    if not all(k in values for k in required_fields):
        return jsonify({'message': 'Missing fields'}), 400

    # if values['sender'] in blockchain.user and values['recipient'] in blockchain.user:
        # sender = hashlib.sha256(values['sender'].encode()).hexdigest()
        # recipient = hashlib.sha256(values['recipient'].encode()).hexdigest()

        #blockchain.sender.append(sender)
        #blockchain.recipient.append(recipient)
        #blockchain.amount.append(values['amount'])


    blockchain.sender = values['sender'];
    blockchain.recipient = values['recipient'];
    blockchain.amount = round(float(values['amount']), 2);
    blockchain.password = values['password'];

    # sender = ''.join([char for index, char in enumerate(values['sender']) if index != 0])

    password = blockchain.generate_sha256(blockchain.password)

    if(password == blockchain.user[blockchain.sender]['password']):
        if (float(blockchain.user[values['sender']]['balance']) - blockchain.amount >= 0.000):
            if (values['sender'] != values['recipient']):
                blockchain.user[values['sender']]['balance'] -= blockchain.amount
                blockchain.user[values['recipient']]['balance'] += blockchain.amount
                
                blockchain.delaytransaction.append({
                    'amount' : blockchain.amount,
                    'sender': blockchain.sender,
                    'recipient': blockchain.recipient,
                })
            else:
                return jsonify({'status': "Failed", 'message': "You can't send coin in your own wallet"})
        else:
            return jsonify({'status': "Failed", 'message': 'Your balance not Enough to do Transaction'})

        blockchain.sender = "";
        blockchain.recipient = "";
        blockchain.amount = "";
        blockchain.password = "";

        return jsonify({'status': "Successfully", 'message': 'Transaction successfully created'}), 200
    else:
        return jsonify({'status': "Failed", 'message': 'Transaction failed'}), 400

# add nodes 
@app.route('/add/node', methods=['GET'])
def add_node():
    values = request.get_json()

    if(values['node']):
        blockchain.addnode = values['node']
        blockchain.add_nodes()
        for node in blockchain.nodes:
            requests.get(f'http://{node}/nodes/sync')

        return jsonify({'message': 'Nodes berhasil di tambahkan'})


# route multiple nodes

@app.route('/nodes/sync', methods=['GET'])
def sync():
    blockchain.update_blockchain()
    response = {
           'status': "Successfully",
           'message': 'blockhain already update',
           'nodes': list(blockchain.nodes)
    }
    return jsonify(response), 200


if __name__ == '__main__':
    app.run(host="0.0.0.0", port=int(sys.argv[1]))



