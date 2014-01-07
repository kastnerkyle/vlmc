""" <amarmlal [at] gmail [dot] com>
	amlal on github/bitbucket

	Distributed under GNU GPL.

	This is a variable-length Markov chain based on the prefix-tree structure described in Francois Pachet's
	work on the Continuator. Branch classes represent the 'tree branches' of the prefix tree. A single Tree
	class will contain several branches, encompassing the entire model. The Continuator class contains
	wrapper methods for interacting with this tree structure using the paradigm of Finite-State Automata.
	Methods include parsing sequences into the tree, generating new states (based on previous states), 
	repeating states, or traversing backwards to a previously generated state in order to move in a different
	next direction. More than 3 repeated states cannot be generated by the new state generator. Working on methods
	to break loops of longer lengths.

	In order to initiate this class,

		model = Continuator(symbolic_seq,dictionary1,dictionary2,boundaries,maxlen)

	where: 
		'symbolic_seq' is the sequence of symbols you wish to model. This program is designed to work with a 
		list or np.ndarray of chars. This also applies the limitation that there cannot be more than 94 unique
		symbols in the sequence.

		'dictionary1' and 'dictionary2' contain features or vectors associated with each of the unique symbols in
		the symbolic sequence. These are included so the model can be pickled and used independentaly of an 
		analysis method. In future versions, you will be able to use the model without these.

		'boundaries' are the list location indices of boundaries that should be used to segment the symbolic 
		sequence. In the context of music, these are used to segment the symbolic sequence into phrases.

		'maxlen' is the maximum allowed phrase length. This will be deprecated eventually.

	For further interaction, 

		new_state, associated_vec1, associated_vec2 = model(type="next")
	
		previous_state, associated_vec1, associated_vec2 = model(type="prev")
	
		same_state, associated_vec1, associated_vec2 = model(type="repeat")
	
		model.printTree() prints the tree branch by branch
	
		the default __repr__ method prints the current memory of generated states


	more to come....
	"""



from random import choice
from numpy import append,array

class Branch(object):
	"""Sub-branches of class Tree"""

	def __init__(self,sequence,cont_idx):
		self.toplvl = {} #dictionary of nodes at this level and continuation indices
		self.subtrees = {} #dictionary of Continuator subtrees corresponding to each key in toplvl
		
		self.parse_seq(sequence,cont_idx)


	def parse_seq(self,sequence,cont_idx):
		""" Parses entire sequence recusrively"""

		topnode = sequence[1]
		
		if len(sequence) > 2:
			child = sequence[2]
		else:
			child = []

		#if top element of sequence not in the keys, add it
		if topnode not in self.toplvl.keys():
			self.toplvl[topnode] = []


		#if continuation index not in list for node, add it
		if cont_idx not in self.toplvl[topnode]:
			self.toplvl[topnode].append(cont_idx)


		if child:
			if len(sequence[1::]) > 1:
				
				#if the child is already a subtree
				if child in self.subtrees.keys():
					#add the continuation index
					self.subtrees[child].toplvl[child].append(cont_idx)
					self.subtrees[child].parse_seq(sequence[1::],cont_idx)
				else:
					#self.subtrees[child] = []
					#self.subtrees[child].append(Branch(sequence[1::],cont_idx))
					self.subtrees[child] = Branch(sequence[1::],cont_idx)


	def printbranch(self):
		""" Prints branch recursively"""

		print "Node: ", self.toplvl
		print "Corresponding subnodes: ", self.subtrees.keys()
		if self.subtrees:
			for symbol in self.subtrees.keys():
				print "Nodes below ", self.toplvl.keys(), ": ", self.subtrees[symbol].printbranch()
				





class Tree(object):
	"""Top-level of tree for Continuator, designed to work with Branch"""

	def __init__(self,sequence,boundaries,maxphraselen):
		self.topbranch = {}
		self.length = maxphraselen
		self.parse_sequence(sequence,boundaries)
			

	def __repr__(self):
		for symbol in self.topbranch:
			print "BRANCH"
			self.topbranch[symbol].printbranch()
		return ""


	def parse_sequence(self,sequence,boundaries):
		""" Uses self.segments to break sequence into chunks defined by boundaries, 
			passes chunks to self.parse_subsequence"""

		#for each subsequence
		for subsequence,idx in self.segments(sequence,boundaries):
			self.parse_subsequence(subsequence,idx)


	def parse_subsequence(self,subsequence,idx):
		""" Parses each subsequence, first by flipping, then by looking for 
			first (most recent) event in top-level. Creates a new branch for each
			element not in top level. Recursively parses each subsequence
			NOTE: obj.parse_seq uses the Branch parse sequence method, NOT the
			Tree method """

		#flip subsequence
		subsequence = subsequence[::-1]
		#create a branch for each existing internal sequence within subsequence
		while len(subsequence)>= 2:
			cont_idx = len(subsequence) + idx #get continuation index
			if subsequence[1] in self.topbranch:
				obj = self.topbranch[subsequence[1]]
				obj.parse_seq(subsequence,cont_idx)
			else:
				self.topbranch[subsequence[1]] = Branch(subsequence,cont_idx)
			subsequence = subsequence[1::]


	
	def segments(self,sequence,boundaries):
		idx = 0
		#add leading 0
		if boundaries[0] != 0:
			boundaries = append(0,boundaries)
		#add last frame index
		boundaries = append(boundaries,len(sequence))

		for i in range(0,len(boundaries)-1):
			idx = boundaries[i]
			section = sequence[boundaries[i]:boundaries[i+1]]
			yield section,idx


	def splitter(self,seq,size):

		"""break sequence 'seq' into chunks size 'size', return matrix"""
		idx = 0
		while idx<= (len(seq)-1):
			yield seq[idx:idx+size], idx
			idx += size




class Continuator(object):
	"""Wrapper methods for interacting with Tree structure"""

	def __init__(self,sequence,chord_dictionary,timbre_dictionary,boundaries,maxphraselen):
		self.chord_dictionary = chord_dictionary
		self.timbre_dictionary = timbre_dictionary
		self.tree = Tree(sequence,boundaries,maxphraselen)
		self.generated = []
		self.sequence = sequence
		self.buffer_t = []
		self.buffer_c = []
		self.hugedumb_c = []
		self.hugedumb_sym = []

	def __call__(self,type,newgeneration=None):
		""" Call to generate next state based on sequence of played notes
			NOTE: More than 3 repetitions in a row are not allowed. """
		
		#allow the user to pass a symbolic sequence and receive a generation
		if newgeneration:
			print "Warning: previously stored generations will be overwritten"
			self.generated = newgeneration
			self.truncate_generation() #just in case sequence is longer than allowed
			#OVERRIDE TYPE TO NEW
			type=="next"		
		
		if type=="next":
			chordvec, timbrevec = self.generate()
			self.rebuffer(chordvec,timbrevec)
		elif type=="prev":
			chordvec, timbrevec = self.previous()
		elif type=="repeat":
			chordvec, timbrevec = self.repeat()
		else:
			print "Improper usage, type must be 'next', 'prev', 'repeat'"
			chordvec, timbrevec = self.repeat()
		
		
		if self.generated:
			if len(self.generated)==1:
				self.hugedumb_sym = self.generated
			else:
				self.hugedumb_sym = append(self.hugedumb_sym,self.generated[len(self.generated)-1])
		self.hugedumb_c.append(chordvec)
		


		return self.generated, chordvec, timbrevec
		
		

	def __repr__(self):
		return "Generated sequence: %s" % ",".join(self.generated)

	"""MAIN METHODS"""

	def generate(self):
		""" Generates a new state based on past states """
		#if not the first call, get next continuation index


		if self.generated:

			cont,new = self.search(self.generated[::-1])

			#break into new sequence if 3 repetitions, for breaking infinite loops
			if len(self.generated)>=3:
				new = self.breakloops()

			#caveat for new sequences
			if new:
				print "New sequence!"
				pick = self.newstate()
				cont = self.getcont(self.tree.topbranch[pick].toplvl[pick])
				self.addstate(cont-1)
				print "Got continuation index ", cont, ", Symbol ", pick
				return self.chord_dictionary[pick], self.timbre_dictionary[cont]
			else:
				pick = cont-1
				print "Got continuation index ", cont, ", Symbol ", self.sequence[pick]
				self.addstate(pick) #-1 for proper access to original sequence
				return self.chord_dictionary[self.sequence[pick]],self.timbre_dictionary[pick]

		#if the first call, randomly pick a starting branch
		else:
			pick = self.newstate()
			cont = self.getcont(self.tree.topbranch[pick].toplvl[pick])
			print "Got continuation index ", cont, ", Symbol ", pick
			return self.chord_dictionary[pick], self.timbre_dictionary[cont-1]

	def previous(self):
		""" Can repeat up to two previous states 
			NOTE: sets most state to be the output, erasing previously most recent state"""
		if len(self.buffer_c) > 1:
			cv = self.buffer_c[len(self.buffer_c)-2]
			tv = self.buffer_t[len(self.buffer_t)-2]
			self.buffer_c = self.buffer_c[0:len(self.buffer_c)-1]
			self.buffer_t = self.buffer_t[0:len(self.buffer_t)-1]
			#truncate generation
			self.generated = self.generated[0:len(self.generated)-1]
			print "Previous State: ", self.generated[len(self.generated)-1]
		else:
			print "Maximum previous stored elements exceeded, repeating last state instead: "
			cv, tv = self.repeat()
		return cv, tv


	def repeat(self):
		""" Can repeat the most recent state """
		print "Repeating most recent state: ", self.generated[len(self.generated)-1]
		return self.buffer_c[len(self.buffer_c)-1], self.buffer_t[len(self.buffer_t)-1]



	"""SUBROUTINES"""


	def addstate(self,idx):
		""" Appends state at sequence[idx] to self.generated, truncates if necessary """
		self.generated.append(self.sequence[idx]) # append new generation
		self.truncate_generation() #make sure generation is only of max length of tree


	def breakloops(self):
		lent = len(self.generated)
		if self.generated[lent-1] == self.generated[lent-2]:
				if self.generated[lent-2] == self.generated[lent-3]:
					self.generated = []
					return True
		return False


	def getcont(self,idx):
		""" Choose a continuation index from list if list, else return index """
		if isinstance(idx,list):
			return choice(idx)
		else:
			return idx


	def in_branch(self,sequence):
		""" Searches for sequence in all branches. 
			Returns:
				(True, most recent symbol, continuation list) if found
				(False, None, None) if not found 
		"""

		print "Search for ", sequence[::-1]

		#base case
		if len(sequence) == 1:
			if sequence[0] in self.tree.topbranch:
				return True,sequence[0],self.tree.topbranch[sequence[0]].toplvl[sequence[0]]
			else:
				#this will also keep from running the search on sequence length 0 I think
				return False, None, None
		
		#if sequence is longer than 1
		else:
			#if the first symbol is in the top branch
			if sequence[0] in self.tree.topbranch:
				#search subtree
				branch = self.tree.topbranch[sequence[0]]


				#if in subtrees
				if self.in_subtrees(sequence[1::],branch):
					return True,sequence[0],self.tree.topbranch[sequence[0]].toplvl[sequence[0]]

				else:
					return False, None, None,
			else:
				return False, None, None


	def in_subtrees(self,sequence,branch):
		""" Searches given branch and its sub-branches for sequence
			Returns:
				True if found
				False if not found 
		"""

		#if there are sub-branches to search, search them
		if branch.subtrees:
			#if the first element is a sub-tree of this branch
			if sequence[0] in branch.subtrees.keys():
				#if there's a next element
				if sequence[1::]:
					#look for it in the corresponding subbranch
					self.in_subtrees(sequence[1::],branch.subtrees[sequence[0]])
					return True
				else:
					return True
			else:
				return False
		else:
			return False


	def newstate(self):
		""" Generates a new starting state if necessary
			Returns: Symbol from topbranch keys"""

		pick = choice(self.tree.topbranch.keys())
		self.generated = [pick]
		return pick


	def printTree(self):
		for symbol in self.tree.topbranch:
			print "BRANCH"
			self.tree.topbranch[symbol].printbranch()


	def rebuffer(self,cv,tv):
		""" Adds chord vec cv and timbre vec tv to self.buffer1
			Shuffles self.buffer1 to self.buffer2 to have a 2-state memory """

		self.buffer_c.append(cv)
		self.buffer_t.append(tv)
		if len(self.buffer_c) > self.tree.length:
			self.buffer_c = self.buffer_c[1::]
		if len(self.buffer_t) > self.tree.length:
			self.buffer_t = self.buffer_t[1::]


	def search(self,sequence):
		""" Searches for given sequence in Tree, returns continuation index for next symbol,
			and appends generated symbol to self.generated """

		#if sequence found in any branch
		truth,symbol,idx = self.in_branch(sequence)
		
		#if found, return continuation index
		if truth:
			return self.getcont(idx), False
		
		#base case for most recent element not found in tree
		else:
			sequence = sequence[0:len(sequence)-1]
			while len(sequence)>=1:
				truth,symbol,idx = self.in_branch(sequence)
				if truth:
					return self.getcont(idx), False
				else:
					sequence = sequence[0:len(sequence)-1]
			#generate a new state
			pick = self.newstate()
			return self.getcont(self.tree.topbranch[pick].toplvl[pick]), True


	def truncate_generation(self):
		""" Removes oldest generation to bring length of sequence back down to max tree length"""

		while len(self.generated) > self.tree.length:
			self.generated = self.generated[1::]

