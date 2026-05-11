import sys
import hashlib
import json
import requests
import uuid
from time import time
from urllib.parse import urlparse
from flask import Flask, render_template, request, jsonify

class Blockchain(object):
    difficulty_bits = 20
    difficulty_target = 2**(256 - difficulty_bits)

    def __init__(self):
        self.initial_reward = 50.0
        self.halving_interval = 210000
        self.nodes = set() 
        self.user = {}      
        self.delaytransaction = [] 
        self.chain = []
        self.current_pof = []

        genesis_hash = self.hash_block({"message": "genesis_block"})
        self.append_block(nonce=100, hash_of_previous_block=genesis_hash)

    def hash_block(self, block):
        block_encoded = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_encoded).hexdigest()

    def add_nodes(self, address):
        parsed_url = urlparse(address)
        node_netloc = parsed_url.netloc if parsed_url.netloc else parsed_url.path
        if not node_netloc:
            return False, "Invalid URL"

        try:
            # Validasi node sebelum ditambahkan
            response = requests.get(f'http://{node_netloc}/blockchain', timeout=2)
            if response.status_code == 200:
                self.nodes.add(node_netloc)
                return True, "Node validated and added"
        except:
            pass
        return False, "Could not connect to node"

    def valid_chain(self, chain):
        last_block = chain[0]
        current_index = 1

        while current_index < len(chain):
            block = chain[current_index]
            
            # 1. Validasi integritas hash
            if block['hash_of_previous_block'] != self.hash_block(last_block):
                return False

            # 2. Validasi Proof of Work
            if not self.valid_proof(block['index'], block['hash_of_previous_block'], block['transaction'], block['nonce']):
                return False

            last_block = block
            current_index += 1
        return True

    def update_blockchain(self):
        """
        Konsensus: Mengganti chain lokal dengan yang terpanjang di jaringan.
        """
        neighbours = self.nodes
        new_chain = None
        max_length = len(self.chain)

        for node in neighbours:
            try:
                response = requests.get(f'http://{node}/blockchain', timeout=3)
                if response.status_code == 200:
                    length = response.json()['length']
                    chain = response.json()['chain']

                    # Panjang panjangan Manuk
                    if length > max_length and self.valid_chain(chain):
                        max_length = length
                        new_chain = chain
            except:
                continue

        if new_chain:
            self.chain = new_chain
            self.user = self.chain[-1].get('user', {})
            return True
        return False

    def proof_of_work(self, index, hash_of_previous_block, transaction):
        nonce = 0
        while not self.valid_proof(index, hash_of_previous_block, transaction, nonce):
            nonce += 1
        return nonce

    def valid_proof(self, index, hash_of_previous_block, transaction, nonce):
        content = f'{index}{hash_of_previous_block}{transaction}{nonce}'.encode()
        content_hash = hashlib.sha256(content).hexdigest()
        return int(content_hash, 16) < self.difficulty_target

    def append_block(self, nonce, hash_of_previous_block):
        block = {
            'index': len(self.chain),
            'timestamp': time(),
            'transaction': self.delaytransaction,
            'Pof': self.current_pof,
            'nonce': nonce,
            'hash_of_previous_block': hash_of_previous_block,
            'user': self.user.copy(), # Snapshot saldo harus ikut masuk ke blok
        }

        self.delaytransaction = []
        self.current_pof = []
        self.chain.append(block)
        return block

    def get_current_reward(self):
        halvings = len(self.chain) // self.halving_interval
        return self.initial_reward / (2 ** halvings) if halvings < 64 else 0

    @property
    def last_block(self):
        return self.chain[-1]

# --- API Layer (Flask) ---

app = Flask(__name__)
blockchain = Blockchain()

@app.route('/blockchain', methods=['GET'])
def full_chain():
    # Menghapus trigger sync di sini untuk mencegah Deadlock
    response = {
        'chain': blockchain.chain,
        'length': len(blockchain.chain),
    }
    return jsonify(response), 200

@app.route('/mine', methods=['POST', 'GET'])
def mine_block():
    values = request.get_json()
    if not values or 'wallet' not in values:
        return jsonify({'message': 'Missing wallet address'}), 400

    if values["wallet"] not in blockchain.user:
        return jsonify({'message': 'Wallet not registered'}), 403

    last_block = blockchain.last_block
    last_block_hash = blockchain.hash_block(last_block)
    
    nonce = blockchain.proof_of_work(len(blockchain.chain), last_block_hash, blockchain.delaytransaction)
    
    reward = blockchain.get_current_reward()
    blockchain.current_pof.append({'amount': reward, 'miner': values['wallet']})
    blockchain.user[values['wallet']]['balance'] += reward

    block = blockchain.append_block(nonce, last_block_hash)

    for node in blockchain.nodes:
        try:
            requests.get(f'http://{node}/nodes/sync', timeout=1)
        except:
            pass

    return jsonify({
        'message': "New Block Mined",
        'index': block['index'],
        'hash': blockchain.hash_block(block)
    }), 200

@app.route('/transaction/new', methods=['POST'])
def new_transaction():
    v = request.get_json()
    required = ['sender', 'recipient', 'amount', 'password']
    if not all(k in v for k in required):
        return jsonify({'message': 'Missing data'}), 400

    if v['sender'] not in blockchain.user:
        return jsonify({'message': 'Sender not found'}), 404

    pw_hash = hashlib.sha256(v['password'].encode()).hexdigest()
    if pw_hash != blockchain.user[v['sender']]['password']:
        return jsonify({'message': 'Invalid password'}), 401

    amount = round(float(v['amount']), 2)
    if blockchain.user[v['sender']]['balance'] < amount:
        return jsonify({'message': 'Insufficient balance'}), 400

    blockchain.user[v['sender']]['balance'] -= amount
    blockchain.user[v['recipient']]['balance'] += amount
    
    blockchain.delaytransaction.append({
        'amount': amount,
        'sender': v['sender'],
        'recipient': v['recipient'],
    })

    return jsonify({'message': 'Transaction recorded and waiting for next block'}), 201

@app.route('/user/new', methods=['POST'])
def new_user():
    values = request.get_json()
    if not values or 'password' not in values:
        return jsonify({'message': 'Password required'}), 400

    wallet_id = uuid.uuid4().hex
    pw_hash = hashlib.sha256(values['password'].encode()).hexdigest()
    
    blockchain.user[wallet_id] = {"balance": 0.0, "password": pw_hash}
    return jsonify({'wallet': wallet_id}), 201

@app.route('/add/node', methods=['POST'])
def add_node():
    values = request.get_json()
    if not values or 'node' not in values:
        return "Error node data", 400

    success, message = blockchain.add_nodes(values['node'])
    if success:
        # Langsung sinkronkan chain saat node baru masuk
        blockchain.update_blockchain()
        return jsonify({'message': message, 'total_nodes': list(blockchain.nodes)}), 200
    return jsonify({'message': message}), 400

@app.route('/nodes/sync', methods=['GET'])
def sync():
    replaced = blockchain.update_blockchain()
    return jsonify({
        'message': 'Chain replaced' if replaced else 'Chain is authoritative',
        'length': len(blockchain.chain)
    }), 200

if __name__ == '__main__':
    # CRITICAL: threaded=True
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5000
    app.run(host="0.0.0.0", port=port, threaded=True)
