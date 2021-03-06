from ...imports import *
from ... import utils as U

class ZeroShotClassifier():
    """
    interface to Zero Shot Topic Classifier
    """

    def __init__(self, model_name='facebook/bart-large-mnli', device=None):
        """
        ZeroShotClassifier constructor

        Args:
          model_name(str): name of a BART NLI model
          device(str): device to use (e.g., 'cuda', 'cpu')
        """
        if 'mnli' not in model_name and 'xnli' not in model_name:
            raise ValueError('ZeroShotClasifier requires an MNLI or XNLI model')
        try:
            import torch
        except ImportError:
            raise Exception('ZeroShotClassifier requires PyTorch to be installed.')
        self.torch_device = device
        if self.torch_device is None: self.torch_device = 'cuda' if torch.cuda.is_available() else 'cpu'
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(self.torch_device)


    def predict(self, doc, topic_strings=[], include_labels=False, batch_size=8):
        """
        zero-shot topic classification
        Args:
          doc(str): text of document
          topic_strings(list): a list of strings representing topics of your choice
                               Example:
                               topic_strings=['political science', 'sports', 'science']
                               NOTE: len(topic_strings) is treated as batch_size.
                               If the number of topics is greater than a reasonable batch_size
                               for your system, you should break up the topic_strings into 
                               chunks and invoke predict separately on each chunk.
          include_labels(bool): If True, will return topic labels along with topic probabilities
          batch_size(int): batch_size to use. default:8
                           Increase this value to speed up predictions - especially
                           if len(topic_strings) is large.
        Returns:
          inferred probabilities
        """
        if topic_strings is None or len(topic_strings) == 0:
            raise ValueError('topic_strings must be a list of strings')
        if batch_size > len(topic_strings): batch_size = len(topic_strings)
        topic_chunks = list(U.list2chunks(topic_strings, n=math.ceil(len(topic_strings)/batch_size)))
        if len(topic_strings) >= 100 and batch_size==8:
            warnings.warn('TIP: Try increasing batch_size to speedup ZeroShotClassifier predictions')
        result = []
        for topics in topic_chunks:
            pairs = []
            for topic_string in topics:
                premise = doc
                hypothesis = 'This text is about %s.' % (topic_string)
                pairs.append( (premise, hypothesis) )
            batch = self.tokenizer.batch_encode_plus(pairs, return_tensors='pt', padding='longest').to(self.torch_device)
            logits = self.model(batch['input_ids'], attention_mask=batch['attention_mask'])[0]
            entail_contradiction_logits = logits[:,[0,2]]
            probs = entail_contradiction_logits.softmax(dim=1)
            true_probs = list(probs[:,1].cpu().detach().numpy())
            if include_labels:
                true_probs = list(zip(topics, true_probs))
            result.extend(true_probs)
        return result

