#! /usr/bin/python3
# -*- coding:utf-8 -*-
# @Time  : 18-8-30 下午4:02
# Author : TJJ
from config import opt
from utils.visualize import Visualizer
import models
from data.dataset import DogCat
from torch.utils.data import DataLoader
import torch as t
from torchnet import meter
from tqdm import tqdm
from torch.autograd import Variable
import numpy as np
import ipdb
# 进度条
def train(**kwargs):
    opt.parse(**kwargs)
    # step1: configure model
    model = getattr(models,opt.model)(opt.num_class)
    if opt.load_model_path:
        model.load(opt.load_model_path)
    if opt.use_gpu:
        model.cuda()

    # step2: data
    train_data = DogCat(opt.train_data_path, transform=opt.train_transform, train = True)
    val_data = DogCat(opt.train_data_path, transform=opt.test_val_transform, train = False, test= False)
    train_dataloader = DataLoader(train_data, batch_size= opt.batch_size, shuffle=opt.shuffle, num_workers=opt.num_workers)
    val_dataloader   = DataLoader(val_data,   batch_size= opt.batch_size, shuffle=opt.shuffle, num_workers=opt.num_workers)

    # step3: criterion and optimizer
    criterion = t.nn.CrossEntropyLoss()
    lr = opt.lr
    optimizer = t.optim.Adam(params=model.parameters(), lr=lr, weight_decay=opt.weight_decay)

    # step4: meters
    loss_meter = meter.AverageValueMeter()                   # 用于统计一个epoch内的平均误差
    confusion_matrix = meter.ConfusionMeter(opt.num_class)
    previous_loss=1e6
    # step5: train
    vis  = Visualizer(opt.env)
    for epoch in range(opt.max_epoch):
        loss_meter.reset()
        confusion_matrix.reset()

        for ii,(data, label) in tqdm(enumerate(train_dataloader)):
            # train model
            input = Variable(data)
            target  = Variable(label)
            if opt.use_gpu:
                input = input.cuda()
                target = target.cuda()
            optimizer.zero_grad()
            score = model(input)
            loss = criterion(score,target)
            loss.backward()
            optimizer.step()

            loss_meter.add(loss.data)
            confusion_matrix.add(score.data, target.data)

            # ipdb.set_trace()
            if ii%opt.print_freq == opt.print_freq-1:
                vis.plot(win='loss', y=loss_meter.value()[0])

        model.save()

        # step6: validate and visualize
        val_confusion_matrix, val_accuracy = val(model, val_dataloader)
        vis.plot(win='val_accuracy',y=val_accuracy)
        vis.log(win='log_text', info=
                'epoch:{epoch}, lr:{lr}, loss:{loss}, train_cm:{train_cm}, val_cm:{val_cm}'.format(
                    epoch=epoch,lr=lr,loss=loss_meter.value()[0],train_cm=str(confusion_matrix.value()),val_cm=str(val_confusion_matrix)
                )
                )

        # step7: update learning_rate
        if loss_meter.value()[0] > previous_loss:
            lr=lr*opt.lr_decay
            for param_group in optimizer.param_groups:
                param_group['lr']=lr

        previous_loss=loss_meter.value()[0]

def val(model, dataloader):
    """

    :param model:
    :param dataloader:
    :return:
    """
    # step1: set the model to validation mode
    model.eval()
    confusion_matrix = meter.ConfusionMeter(opt.num_class)
    # step2: validate
    for ii,(val_data,label) in tqdm(enumerate(dataloader)):
        input = Variable(val_data, volatile = True)
        if opt.use_gpu:
            input = input.cuda()
        score = model(input)
        confusion_matrix.add(score.data, label)
    # step3: set the model to training mode
    model.train()
    # step4: calculate the accuracy and confusion_matrix
    cm_value = confusion_matrix.value()
    accuracy = 100.0 * np.trace(cm_value)/cm_value.sum()

    return confusion_matrix, accuracy

def test(**kwargs):
    opt.parse(**kwargs)
    result = []
    # step1: configure model and set the model to validation mode
    model = getattr(models,opt.model)(opt.num_class).eval()
    if opt.load_model_path:
        model.load(opt.load_model_path)
    if opt.use_gpu:
        model.cuda()

    # step2: data
    test_data = DogCat(opt.test_data_path, transform=opt.test_val_transform, train=False, test=True)
    test_dataloader = DataLoader(test_data, batch_size=opt.batch_size, shuffle=opt.shuffle, num_workers=opt.num_workers)

    # step3: test
    for ii,(data, label) in tqdm(enumerate(test_dataloader)):
        input = Variable(data)

        if opt.use_gpu:
            input = input.cuda()
        score = model(input)
        # step4: record results
        probability = t.nn.functional.softmax(1.0*score,dim=1).data[:,0].tolist()
        # label = score.max(dim=1)[1].data.tolist()

        batch_results = [(label_, probability_) for label_, probability_ in zip(label, probability)]
        result = result + batch_results

    # step5: write into csv
    write_csv(result,opt.result_file)

def write_csv(result,result_file):
    import csv
    heading = ['id','label']
    with open(result_file,'w') as f:
        writer = csv.writer(f)
        writer.writerow(heading)
        writer.writerows(result)

def help():
    """
    python file.py help
    :return:
    """
    print("""
    usage : python file.py <function> [--args=value]
    <function> := train | test |help
    example:
            python {0} train --env='env0701' --lr=0.01
            python {0} test --dataset='path/to/dataset/root/'
            python {0} help
    aviable args: """.format(__file__)

    )

    from inspect import getsource
    source = getsource(opt.__class__)
    print(source)

if __name__ == '__main__':
    import fire
    fire.Fire()


